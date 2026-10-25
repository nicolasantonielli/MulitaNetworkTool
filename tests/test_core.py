import os
import unittest
from pathlib import PurePosixPath
from types import SimpleNamespace
from unittest.mock import patch

from mulita.config import Binaries
from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.models import (Calibration, CaptureDirection, ClimateReading,
                                CommandResult)
from mulita.core.parsers import cable_connected, parse_interfaces, parse_speed_test

IP_JSON = '''[
 {"ifindex":1,"ifname":"lo","address":"00:00:00:00:00:00",
  "addr_info":[{"family":"inet","local":"127.0.0.1"}]},
 {"ifindex":2,"ifname":"eth0","address":"b8:27:eb:00:00:01","addr_info":[]},
 {"ifindex":3,"ifname":"wlan0","address":"b8:27:eb:00:00:02",
  "addr_info":[{"family":"inet","local":"192.168.0.20"},{"family":"inet6","local":"fe80::1"}]}
]'''


class CommandFactoryTest(unittest.TestCase):
    """Mismos comandos que armaba la version anterior, sin pasar por el shell."""

    def setUp(self):
        self.commands = CommandFactory(Binaries())

    def test_capture_writes_into_capture_dir(self):
        request = validation.capture_request('eth0', 'inout', 'prueba')
        self.assertEqual(
            self.commands.capture(request, PurePosixPath('/root/capturas')),
            ['/bin/tcpdump', '-Q', 'inout', '-i', 'eth0', '-w', '/root/capturas/prueba.pcap'])

    def test_trace(self):
        self.assertEqual(self.commands.trace('8.8.8.8', 6),
                         ['/bin/mtr', '8.8.8.8', '-n', '-r', '-c', '6'])

    def test_ping_with_count(self):
        request = validation.ping_request('8.8.8.8', 4, 1, 64)
        self.assertEqual(self.commands.ping(request),
                         ['/bin/ping', '8.8.8.8', '-n', '-c', '4', '-i', '1.00', '-s', '56'])

    def test_ping_zero_count_is_continuous(self):
        request = validation.ping_request('8.8.8.8', 0.4, 0.1000001, 2048)
        self.assertEqual(self.commands.ping(request),
                         ['/bin/ping', '8.8.8.8', '-n', '-i', '0.10', '-s', '2040'])

    def test_scan_keeps_extra_nmap_arguments(self):
        args = validation.scan_arguments('-p 22,80 192.168.0.0/24')
        self.assertEqual(self.commands.port_scan(args),
                         ['/bin/nmap', '-p', '22,80', '192.168.0.0/24'])

    def test_misc_commands(self):
        self.assertEqual(self.commands.discovery(), ['/sbin/netdiscover', '-f', '-P', '-d'])
        self.assertEqual(self.commands.speed_test(), ['/bin/speedtest', '--json'])
        self.assertEqual(self.commands.update('/repo', 'origin', 'v3'),
                         ['/usr/bin/git', '-C', '/repo', 'pull', 'origin', 'v3'])
        self.assertEqual(self.commands.restart_service('mulita'),
                         ['/usr/bin/systemd-run', '--collect', '--no-block',
                          '/usr/bin/systemctl', 'restart', 'mulita'])
        self.assertEqual(self.commands.interfaces(), ['/usr/bin/ip', '-j', 'addr'])


class ValidationTest(unittest.TestCase):

    def test_host_rejects_shell_injection_and_options(self):
        for value in ('8.8.8.8; poweroff', '-f', '', '   ', 'a b'):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validation.host(value)

    def test_host_accepts_ip_names_and_ipv6(self):
        for value in ('8.8.8.8', 'google.com', 'fe80::1%eth0', ' 10.0.0.1 '):
            with self.subTest(value=value):
                self.assertEqual(validation.host(value), value.strip())

    def test_capture_filename(self):
        self.assertEqual(validation.capture_filename('prueba'), 'prueba.pcap')
        self.assertEqual(validation.capture_filename('prueba.pcap'), 'prueba.pcap')
        for value in ('../x', 'a/b', '', 'a b'):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validation.capture_filename(value)

    def test_capture_requires_interface_and_direction(self):
        with self.assertRaises(ValidationError):
            validation.capture_request('', 'in', 'x')
        with self.assertRaises(ValidationError):
            validation.capture_request('eth0', '', 'x')
        request = validation.capture_request('eth0', 'out', 'x')
        self.assertIs(request.direction, CaptureDirection.SALIENTE)

    def test_mac(self):
        self.assertEqual(validation.mac_address('AA:bb:cc:dd:ee:ff'), 'AA:bb:cc:dd:ee:ff')
        self.assertEqual(validation.mac_address('aa-bb-cc-dd-ee-ff'), 'aa-bb-cc-dd-ee-ff')
        for value in ('aa:bb:cc:dd:ee', 'aa:bb-cc:dd:ee:ff', 'zz:bb:cc:dd:ee:ff; ls'):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validation.mac_address(value)

    def test_ping_ranges(self):
        with self.assertRaises(ValidationError):
            validation.ping_request('8.8.8.8', 21, 1, 64)
        with self.assertRaises(ValidationError):
            validation.ping_request('8.8.8.8', 4, 1, 32)


class VersionTest(unittest.TestCase):

    def test_semantic_version_from_2_0_0(self):
        from mulita.version import __version__
        parts = tuple(int(part) for part in __version__.split('.'))
        self.assertEqual(len(parts), 3)
        self.assertGreaterEqual(parts, (2, 0, 0))


class ParsersAndModelsTest(unittest.TestCase):

    def test_interfaces(self):
        interfaces = parse_interfaces(IP_JSON)
        self.assertEqual([i.name for i in interfaces], ['lo', 'eth0', 'wlan0'])
        self.assertEqual(interfaces[1].addresses, ())
        self.assertEqual(interfaces[2].addresses, ('192.168.0.20', 'fe80::1'))
        self.assertEqual(interfaces[2].mac, 'b8:27:eb:00:00:02')
        self.assertFalse(interfaces[1].cable)

    def test_cable_is_up_ethernet_with_carrier(self):
        self.assertTrue(cable_connected('eth0', ['UP', 'LOWER_UP'], 'UP'))
        self.assertFalse(cable_connected('eth0', ['NO-CARRIER', 'UP'], 'DOWN'))
        self.assertFalse(cable_connected('wlan0', ['UP', 'LOWER_UP'], 'UP'))
        self.assertFalse(cable_connected('lo', ['UP', 'LOWER_UP'], 'UNKNOWN'))

    def test_speed_test(self):
        result = parse_speed_test('{"download": 93450000.5, "upload": 11200000}')
        self.assertAlmostEqual(result.download_mbps, 93.4500005)
        self.assertAlmostEqual(result.upload_mbps, 11.2)
        with self.assertRaises(CommandFailedError):
            parse_speed_test('Cannot retrieve speedtest configuration')

    def test_calibration(self):
        calibrated = Calibration(temperature_offset=-6, humidity_offset=15).apply(ClimateReading(35, 63))
        self.assertEqual(calibrated, ClimateReading(29, 78))

    def test_command_result_text(self):
        self.assertEqual(CommandResult(0, 'out', 'warn').text, 'out')
        self.assertEqual(CommandResult(1, 'out', 'boom').text, 'out\nboom')
        self.assertEqual(CommandResult(1, '', 'boom').text, 'boom')


class HomeEnvironmentTest(unittest.TestCase):

    def test_missing_home_comes_from_the_account(self):
        import sys
        from mulita.bootstrap import _ensure_home

        fake = SimpleNamespace(getpwuid=lambda _uid: SimpleNamespace(pw_dir='/root'))
        saved = os.environ.copy()
        saved.pop('HOME', None)
        with patch.dict(os.environ, saved, clear=True), \
                patch.dict(sys.modules, {'pwd': fake}), \
                patch('mulita.bootstrap.os.getuid', return_value=0, create=True):
            _ensure_home()
            self.assertEqual(os.environ['HOME'], '/root')


if __name__ == '__main__':
    unittest.main()
