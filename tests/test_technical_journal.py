"""Journal behavior at use-case boundaries, without Qt controllers."""
import ast
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mulita.adapters.settings_store import MemorySettingsStore
from mulita.bootstrap import build_services
from mulita.config import AppConfig
from mulita.core.events import OperationEvent
from mulita.core.errors import AlreadyRunningError, ValidationError
from mulita.core.models import (CommandResult, PingSummary, TraceHop, PortFinding,
                                SpeedTestResult, ClimateReading, EthernetConfig)
from mulita.core.settings import Settings
from mulita.presentation.journal import render_event
from tests.fakes import FakeRunner, FakeCommand, FakeStorage
from mulita.core.platform import UsbDrive


class TechnicalJournalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = AppConfig(test_mode=True, capture_dir=self.root / 'captures',
                                settings_path=self.root / 'settings.json')
        self.runner = FakeRunner()
        self.services = build_services(self.config, runner=self.runner,
            settings_store=MemorySettingsStore(Settings(technical_journal=True)))

    def text(self):
        return ''.join(path.read_text(encoding='utf-8') for path in
                       sorted((self.config.capture_dir / 'bitacora').glob('*.txt')))

    def test_direct_ping_records_chunked_results_once_without_ui(self):
        self.services.ping.start('8.8.8.8', 2, 1, 64)
        self.runner.outputs[-1]('2 packets trans')
        self.runner.outputs[-1]('mitted, 1 received, 50% packet loss, time 1000ms\n'
                                'rtt min/avg/max/mdev = 9.0/10.0/11.0/0.2 ms')
        self.runner.handles[-1].finish()
        self.runner.handles[-1].finish()
        text = self.text()
        self.assertEqual(text.count('Se hizo ping a 8.8.8.8.'), 1)
        self.assertEqual(text.count('Resultado del ping a 8.8.8.8:'), 1)
        self.assertIn('se enviaron 2 paquetes y se recibió 1 (50% de pérdida)', text)
        self.assertIn('Tiempo medio de respuesta: 10.0 ms.', text)

    def test_settings_apply_without_recreating_services(self):
        self.services.settings.set_technical_journal(False)
        self.services.ping.start('8.8.8.8', 1, 1, 64)
        self.runner.handles[-1].finish()
        self.assertEqual(self.text(), '')
        self.services.settings.set_language('en')
        self.services.settings.set_technical_journal(True)
        self.services.ping.start('1.1.1.1', 1, 1, 64)
        self.runner.handles[-1].finish()
        self.assertIn('A ping was sent to 1.1.1.1.', self.text())
        previous = self.text()
        self.services.settings.set_language('es')
        self.services.ping.start('8.8.8.8', 1, 1, 64)
        self.runner.handles[-1].finish()
        self.assertTrue(self.text().startswith(previous))
        self.assertIn('Se hizo ping a 8.8.8.8.', self.text())

    def test_stopping_and_rejected_second_start_preserve_first_operation(self):
        events = []
        self.services.ping.set_event_sink(events.append)
        self.services.ping.start('8.8.8.8', 1, 1, 64)
        with self.assertRaises(AlreadyRunningError):
            self.services.ping.start('1.1.1.1', 1, 1, 64)
        self.services.ping.stop()
        self.assertEqual([e.phase for e in events], ['started', 'started', 'failed', 'stop', 'completed'])
        self.assertEqual(events[0].operation_id, events[-1].operation_id)
        self.assertEqual(events[-1].parameters['target'], '8.8.8.8')
        self.assertTrue(events[-1].parameters['stopped'])

    def test_failed_process_has_failure_and_partial_results(self):
        self.services.ping.start('8.8.8.8', 1, 1, 64)
        self.runner.handles[-1].finish(2)
        self.assertIn('Falló la operación', self.text())
        self.assertIn('sin estadísticas finales', self.text())

    def test_direct_exports_use_actual_names_and_do_not_record_failed_exports(self):
        (self.config.capture_dir / 'ping').mkdir(parents=True)
        summary = PingSummary(transmitted='1', received='1', loss='0%')
        self.assertEqual(self.services.ping.save((), summary, 'prueba'), 'prueba.csv')
        self.assertEqual(self.text().count('Se exportó el archivo prueba.csv.'), 1)
        self.assertEqual(self.text().count('Se exportó el archivo prueba.statics.csv.'), 1)
        with self.assertRaises(ValidationError):
            self.services.ping.save((), summary, 'prueba')
        self.assertEqual(self.text().count('Se exportó el archivo prueba.csv.'), 1)
        self.assertIn('Falló la operación', self.text())

    def test_usb_batch_exports_record_each_file(self):
        folder = self.config.capture_dir / 'ping'
        folder.mkdir(parents=True)
        for name in ('first.csv', 'second.csv'):
            (folder / name).write_text('data')
        usb = self.root / 'usb'
        usb.mkdir()
        self.services.files._storage = FakeStorage((UsbDrive('sda1', 'USB', str(usb)),))
        self.services.files.export_many([('ping', 'first.csv'), ('ping', 'second.csv')], 'sda1')
        for name in ('first.csv', 'second.csv'):
            self.assertEqual(self.text().count(f'Se exportó el archivo {name}.'), 1)
            self.assertTrue((usb / name).exists())

    def test_wifi_events_never_capture_password_or_error_output(self):
        events = []
        self.services.wifi.set_event_sink(events.append)
        self.runner.results['/usr/bin/nmcli'] = CommandResult(0, 'wlan0:wifi\n')
        self.services.wifi.connect('lab', 'private-password', True)
        self.assertEqual(events[-1].parameters, {'ssid': 'lab'})
        self.assertNotIn('private-password', repr(events))
        for event in events:
            self.services.journal.record(event)
        self.assertIn('Se estableció la conexión Wi-Fi con la red lab.', self.text())
        self.assertNotIn('private-password', self.text())
        with patch.object(self.runner, 'run', side_effect=OSError('secret-error-text')):
            with self.assertRaises(OSError):
                self.services.wifi.connect('lab', 'private-password', True)
        self.assertEqual(events[-1].phase, 'failed')
        self.assertNotIn('secret-error-text', repr(events))

    def test_observer_failure_does_not_change_operation_result_or_callbacks(self):
        def broken(_event):
            raise OSError('disk full')
        self.services.ping.set_event_sink(broken)
        exited = []
        with self.assertLogs('mulita.core.events', level='ERROR'):
            request = self.services.ping.start('8.8.8.8', 1, 1, 64, on_exit=exited.append)
            self.runner.handles[-1].finish()
        self.assertEqual(request.target, '8.8.8.8')
        self.assertEqual(exited, [0])

    def test_capture_finishing_during_launch_uses_returned_filename(self):
        def immediate(argv, on_output=None, on_exit=None, **kwargs):
            command = FakeCommand(on_exit)
            command.finish()
            return command
        with patch.object(self.runner, 'start', side_effect=immediate):
            request = self.services.capture.start('eth0', 'inout', 'capture')
        self.assertIn(f'se guardó en {request.filename}.', self.text())

    def test_service_graph_does_not_load_qt(self):
        subprocess.run([sys.executable, '-c',
            "import sys; from mulita.bootstrap import build_services; "
            "assert not any(name.startswith('PyQt') for name in sys.modules)"], check=True, timeout=15)

    def test_bridge_does_not_produce_technical_journal_entries(self):
        root = Path(__file__).resolve().parents[1] / 'mulita/ui/qt/bridge'
        for path in root.glob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, ('technicalNote', '_note', '_saved_file'), str(path))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == '_tr':
                    if node.args and isinstance(node.args[0], ast.Constant):
                        self.assertFalse(str(node.args[0].value).startswith('journal'), str(path))

    def test_export_names_are_data_not_translation_keys(self):
        for language in ('es', 'en'):
            text = render_event(OperationEvent('export', 'completed', {}, 'ping-{value}.csv'), language)
            self.assertIn('ping-{value}.csv', text[0])
        english = render_event(OperationEvent('ipv4_wifi', 'started', {}), 'en')
        self.assertIn('Wi-Fi IP', english[0])

    def test_all_result_families_render_from_domain_data_in_both_languages(self):
        cases = [
            ('trace', {'target': '8.8.8.8'},
             (TraceHop(1, '192.0.2.1', '0%', '1', '10', '10', '10', '10', '0'),), '192.0.2.1'),
            ('ports', {}, (PortFinding('192.0.2.1', '443', 'tcp', 'open', 'https'),), '443/tcp'),
            ('discovery', {'interface': 'eth0'},
             (SimpleNamespace(ip='192.0.2.1', mac='00:11:22:33:44:55'),), '00:11:22:33:44:55'),
            ('wol', {}, SimpleNamespace(mac='00:11:22:33:44:55', target='255.255.255.255', port='9'), '255.255.255.255'),
            ('climate', {}, ClimateReading(25, 60), '25 °C'),
            ('speed', {}, SpeedTestResult(10000000, 2000000), '10.00'),
            ('public_ip', {}, SimpleNamespace(ip='192.0.2.1'), '192.0.2.1'),
            ('vendor', {'mac': '00:11:22:33:44:55'}, 'Vendor', 'Vendor'),
            ('capture', {'interface': 'eth0', 'exit_code': 0}, SimpleNamespace(filename='capture.pcap'), 'capture.pcap'),
            ('tap', {'config': SimpleNamespace(entrante='eth0', saliente='eth1')}, 'tap.pcap', 'tap.pcap'),
            ('tls', {'target': 'example.org'}, (SimpleNamespace(severity='HIGH'),), ': 1'),
            ('nmap', {'target': '192.0.2.1'},
             SimpleNamespace(hosts=({'ip': '192.0.2.1'},), status='ok', open_ports='443'), '443'),
            ('switch', {}, {'interface': 'eth0', 'cancelled': False, 'frames': 5,
                           'neighbors': [{'name': 'Switch', 'port': 'Gi1/0/1'}]}, 'Gi1/0/1'),
            ('ipv4_ethernet', {'interface': 'eth0'}, EthernetConfig(), 'eth0'),
            ('vlan', {'interface': 'eth0.20', 'enabled': True, 'vlan': '20'}, None, 'eth0.20'),
        ]
        for language in ('es', 'en'):
            for action, parameters, result, expected in cases:
                with self.subTest(language=language, action=action):
                    lines = render_event(OperationEvent(action, 'completed', parameters, result), language)
                    self.assertTrue(lines)
                    self.assertIn(expected, '\n'.join(lines))
                    self.assertNotIn('journal', '\n'.join(lines))


if __name__ == '__main__':
    unittest.main()
