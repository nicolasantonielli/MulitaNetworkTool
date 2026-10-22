import sys
import threading
import unittest

from mulita.adapters.subprocess_runner import SubprocessCommandRunner
from mulita.bootstrap import build_services
from mulita.config import AppConfig
from mulita.core.errors import (AlreadyRunningError, CommandFailedError,
                                ValidationError)
from mulita.core.models import (MISSING_COMMAND_CODE, ClimateReading,
                                CommandResult, TapConfig)
from mulita.core.ports import ClimateSensor
from mulita.services.tools import ClimateService
from tests.fakes import FakeRunner
from tests.test_core import IP_JSON


def services_with(runner: FakeRunner, test_mode: bool = True):
    return build_services(AppConfig(test_mode=test_mode), runner=runner)


class SessionServicesTest(unittest.TestCase):

    def test_capture_start_stop(self):
        runner = FakeRunner()
        services = services_with(runner)
        exits = []
        services.capture.start('eth0', 'in', 'captura', on_exit=exits.append)

        self.assertTrue(services.capture.is_running)
        self.assertEqual(runner.starts[-1][-1], '/root/Desktop/captura.pcap')
        with self.assertRaises(AlreadyRunningError):
            services.capture.start('eth0', 'in', 'otra')

        services.capture.stop()
        self.assertFalse(services.capture.is_running)
        self.assertEqual(runner.handles[-1].signals, ['TERM'])
        self.assertEqual(exits, [-15])

    def test_capture_validation_happens_before_launch(self):
        runner = FakeRunner()
        with self.assertRaises(ValidationError):
            services_with(runner).capture.start('', 'in', 'x')
        self.assertEqual(runner.starts, [])

    def test_ping_stops_with_interrupt_to_keep_statistics(self):
        runner = FakeRunner()
        services = services_with(runner)
        services.ping.start('8.8.8.8', 0, 1, 64)
        services.ping.stop()
        self.assertEqual(runner.handles[-1].signals, ['INT'])
        services.ping.start('8.8.8.8', 4, 1, 64)
        self.assertTrue(services.ping.is_running)

    def test_shutdown_stops_everything(self):
        runner = FakeRunner()
        services = services_with(runner)
        services.capture.start('eth0', 'in', 'x')
        services.ping.start('8.8.8.8', 0, 1, 64)
        services.discovery.start()
        services.tap.start(TapConfig('eth0', 'eth1', 'eth2'))
        services.shutdown()
        self.assertTrue(all(not handle.running for handle in runner.handles))
        self.assertFalse(services.tap.is_running)


class BlockingServicesTest(unittest.TestCase):

    def test_trace_and_scan_return_output(self):
        runner = FakeRunner({'/bin/mtr': CommandResult(0, 'HOST: x\n'),
                             '/bin/nmap': CommandResult(1, '', 'Failed to resolve')})
        services = services_with(runner)
        self.assertEqual(services.trace.trace('8.8.8.8'), 'HOST: x\n')
        self.assertEqual(services.port_scan.scan('nohost'), 'Failed to resolve')

    def test_wake_on_lan_validates_mac(self):
        runner = FakeRunner()
        services = services_with(runner)
        with self.assertRaises(ValidationError):
            services.wake_on_lan.wake('no-mac')
        services.wake_on_lan.wake('aa:bb:cc:dd:ee:ff')
        self.assertEqual(runner.runs[-1], ['/bin/wakeonlan', 'aa:bb:cc:dd:ee:ff'])

    def test_interfaces(self):
        runner = FakeRunner({'/usr/bin/ip': CommandResult(0, IP_JSON)})
        services = services_with(runner)
        self.assertEqual(services.interfaces.names(), ['lo', 'eth0', 'wlan0'])
        self.assertEqual(services.interfaces.addresses(), ['127.0.0.1', '192.168.0.20', 'fe80::1'])

    def test_interfaces_failure_gives_empty_list(self):
        runner = FakeRunner({'/usr/bin/ip': CommandResult(MISSING_COMMAND_CODE, '', 'no ip')})
        self.assertEqual(services_with(runner).interfaces.names(), [])

    def test_speed_test_and_public_ip(self):
        runner = FakeRunner({'/bin/speedtest': CommandResult(0, '{"download": 50e6, "upload": 10e6}'),
                             '/bin/curl': CommandResult(0, '181.1.2.3')})
        services = services_with(runner)
        self.assertEqual(services.speed_test.measure().download_mbps, 50)
        self.assertEqual(services.public_ip.lookup(), '181.1.2.3')

    def test_public_ip_without_answer_fails(self):
        runner = FakeRunner({'/bin/curl': CommandResult(28, '', '')})
        with self.assertRaises(CommandFailedError):
            services_with(runner).public_ip.lookup()

    def test_update_reports_failure(self):
        runner = FakeRunner({'/usr/bin/git': CommandResult(1, '', 'not a git repository')})
        with self.assertRaises(CommandFailedError):
            services_with(runner).maintenance.update()

    def test_test_mode_climate_is_fixed(self):
        reading = services_with(FakeRunner(), test_mode=True).climate.read()
        self.assertEqual(reading, ClimateReading(29, 78))

    def test_failed_sensor_reading_is_none(self):
        class Silent(ClimateSensor):
            def read(self):
                return None
        self.assertIsNone(ClimateService(Silent(), calibration=None).read())


class KeyboardServiceTest(unittest.TestCase):

    def test_toggle_notifies_all_listeners(self):
        runner = FakeRunner()
        keyboard = services_with(runner).keyboard
        first, second = [], []
        keyboard.subscribe(first.append)
        keyboard.subscribe(second.append)

        keyboard.toggle()
        keyboard.toggle()
        self.assertEqual(first, [True, False])
        self.assertEqual(second, [True, False])
        self.assertEqual(runner.starts, [['onboard'], ['killall', 'onboard']])

    def test_missing_onboard_resets_state(self):
        runner = FakeRunner()
        keyboard = services_with(runner).keyboard
        states = []
        keyboard.subscribe(states.append)
        keyboard.show()
        runner.handles[-1].finish(MISSING_COMMAND_CODE)
        self.assertFalse(keyboard.visible)
        self.assertEqual(states, [True, False])


class SubprocessRunnerTest(unittest.TestCase):

    def setUp(self):
        self.runner = SubprocessCommandRunner()

    def test_run(self):
        result = self.runner.run([sys.executable, '-c', 'print("hola")'])
        self.assertTrue(result.ok)
        self.assertEqual(result.stdout.strip(), 'hola')

    def test_missing_command(self):
        result = self.runner.run(['comando-que-no-existe-mulita'])
        self.assertEqual(result.returncode, MISSING_COMMAND_CODE)

    def test_stream_lines_and_exit(self):
        lines, done = [], threading.Event()
        codes = []

        def on_exit(code):
            codes.append(code)
            done.set()

        self.runner.start([sys.executable, '-c', 'print("a"); print("b")'],
                          on_output=lines.append, on_exit=on_exit)
        self.assertTrue(done.wait(10))
        self.assertEqual([line.strip() for line in lines], ['a', 'b'])
        self.assertEqual(codes, [0])

    def test_stream_missing_command_reports_and_exits(self):
        lines, done = [], threading.Event()
        handle = self.runner.start(['comando-que-no-existe-mulita'],
                                   on_output=lines.append, on_exit=lambda code: done.set())
        self.assertTrue(done.wait(5))
        self.assertFalse(handle.running)
        self.assertIn('No se encontro', lines[0])

    def test_terminate_long_process(self):
        done = threading.Event()
        handle = self.runner.start([sys.executable, '-c', 'import time; time.sleep(30)'],
                                   on_exit=lambda code: done.set())
        self.assertTrue(handle.running)
        handle.terminate()
        self.assertTrue(done.wait(10))
        self.assertFalse(handle.running)


if __name__ == '__main__':
    unittest.main()
