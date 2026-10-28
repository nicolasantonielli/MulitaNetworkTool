import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.fakes import FakeRunner
from tests.qt_support import qt_app

from mulita.config import Binaries
from mulita.core.commands import CommandFactory
from mulita.core.errors import AlreadyRunningError, ValidationError
from mulita.core.models import MISSING_COMMAND_CODE
from mulita.core.tls import (grouped, mode_flags, parse_report, parse_target,
                             summarize, test_label)
from mulita.presentation.i18n import use
from mulita.services.tls import TlsService
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.tls import TlsController
from mulita.ui.qt.dispatcher import QtDispatcher

REPORT = [
    {'id': 'cert_commonName', 'ip': 'example.com/93.184.216.34', 'port': '443',
     'severity': 'OK', 'finding': 'example.com'},
    {'id': 'cert_expirationStatus', 'severity': 'HIGH', 'finding': 'expires < 10 days (3)'},
    {'id': 'cert', 'severity': 'INFO', 'finding': '-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----'},
    {'id': 'cert_commonName <cert#2>', 'severity': 'OK', 'finding': 'example.org'},
    {'id': 'TLS1', 'severity': 'high', 'finding': 'offered (deprecated)'},
    {'id': 'TLS1_3', 'severity': 'OK', 'finding': 'offered with\n  final'},
    {'id': 'cipherlist_OBSOLETED', 'severity': 'OK', 'finding': 'not offered'},
    {'id': 'SWEET32', 'severity': 'LOW', 'finding': 'VULNERABLE', 'cve': 'CVE-2016-2183'},
    {'id': 'HSTS', 'severity': 'MEDIUM', 'finding': 'not offered'},
    {'id': 'scanTime', 'severity': 'INFO', 'finding': '12'},
]


def report_text(entries=REPORT):
    return json.dumps(entries)


class TargetTest(unittest.TestCase):
    def setUp(self):
        use('es')

    def test_host_uses_the_default_port(self):
        target = parse_target('example.com')
        self.assertEqual((target.host, target.port), ('example.com', 443))
        self.assertEqual(target.argument, 'example.com:443')

    def test_port_and_url_forms(self):
        self.assertEqual(parse_target('example.com:8443').argument, 'example.com:8443')
        self.assertEqual(parse_target('https://example.com:9443/ruta?x=1').argument, 'example.com:9443')
        self.assertEqual(parse_target('https://user@example.com/').argument, 'example.com:443')
        self.assertEqual(parse_target(' 10.0.0.5 ').argument, '10.0.0.5:443')

    def test_ipv6(self):
        self.assertEqual(parse_target('[::1]:8443').argument, '[::1]:8443')
        self.assertEqual(parse_target('[2001:db8::1]').argument, '[2001:db8::1]:443')
        self.assertEqual(parse_target('2001:db8::1').argument, '[2001:db8::1]:443')

    def test_rejects_bad_targets(self):
        for value in ('', '   ', '-oX', '--help', 'host:0', 'host:99999', 'host:abc',
                      '[::1', '[::1]x', 'host name', 'a;b'):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    parse_target(value)

    def test_modes(self):
        self.assertEqual(mode_flags('certificate'), ['-S'])
        self.assertEqual(mode_flags('full'), ['-S', '-p', '-s', '-U'])
        with self.assertRaises(ValidationError):
            mode_flags('nope')


class ReportTest(unittest.TestCase):
    def setUp(self):
        use('es')

    def test_parses_the_flat_report(self):
        found = parse_report(report_text())
        ids = [item.id for item in found]
        self.assertNotIn('cert', ids)
        self.assertNotIn('scanTime', ids)
        self.assertEqual(ids.count('cert_commonName'), 2)
        self.assertEqual(len(found), 8)

    def test_normalises_severity_text_and_copy(self):
        by_key = {(item.id, item.copy): item for item in parse_report(report_text())}
        self.assertEqual(by_key[('TLS1', 0)].severity, 'HIGH')
        self.assertEqual(by_key[('TLS1_3', 0)].text, 'offered with final')
        self.assertEqual(by_key[('cert_commonName', 2)].text, 'example.org')
        self.assertEqual(by_key[('SWEET32', 0)].cve, 'CVE-2016-2183')

    def test_classifies_sections(self):
        sections = {item.id: item.section for item in parse_report(report_text())}
        self.assertEqual(sections['cert_commonName'], 'certificate')
        self.assertEqual(sections['cert_expirationStatus'], 'certificate')
        self.assertEqual(sections['TLS1'], 'protocols')
        self.assertEqual(sections['cipherlist_OBSOLETED'], 'ciphers')
        self.assertEqual(sections['SWEET32'], 'vulnerabilities')
        self.assertEqual(sections['HSTS'], 'other')

    def test_reads_nested_reports(self):
        nested = {'Invocation': 'testssl', 'scanResult': [{
            'targetHost': 'example.com',
            'protocols': [{'id': 'TLS1_2', 'severity': 'OK', 'finding': 'offered'}],
            'serverDefaults': [{'id': 'cert_commonName', 'severity': 'OK', 'finding': 'example.com'}],
        }]}
        found = parse_report(json.dumps(nested))
        self.assertEqual([item.id for item in found], ['TLS1_2', 'cert_commonName'])

    def test_reads_a_report_cut_short(self):
        text = report_text(REPORT[:2])
        cut = text[:text.rindex('}')]  # el proceso se detuvo a mitad del ultimo hallazgo
        found = parse_report(cut)
        self.assertEqual([item.id for item in found], ['cert_commonName'])

    def test_garbage_gives_nothing(self):
        for text in ('', '   ', 'no es json', '[]', '{}', '[1, 2]'):
            with self.subTest(text=text):
                self.assertEqual(parse_report(text), ())

    def test_labels(self):
        found = {(item.id, item.copy): item for item in parse_report(report_text())}
        self.assertEqual(test_label(found[('cert_commonName', 0)]), 'Nombre común (CN)')
        self.assertEqual(test_label(found[('cert_commonName', 2)]), 'Nombre común (CN) #2')
        self.assertEqual(test_label(found[('TLS1', 0)]), 'TLS 1.0')
        self.assertEqual(test_label(found[('SWEET32', 0)]), 'SWEET32')
        use('en')
        self.assertEqual(test_label(found[('cert_commonName', 0)]), 'Common name (CN)')

    def test_groups_by_section_with_headers(self):
        rows = grouped(parse_report(report_text()))
        headers = [row['title'] for row in rows if row['header']]
        self.assertEqual(headers, ['Certificado', 'Protocolos', 'Cifrados', 'Vulnerabilidades', 'Otros'])
        self.assertTrue(rows[0]['header'])
        sweet = next(row for row in rows if row.get('test') == 'SWEET32')
        self.assertEqual((sweet['severity'], sweet['tone']), ('Bajo', 'warning'))
        self.assertTrue(sweet['result'].endswith('(CVE-2016-2183)'))
        expiry = next(row for row in rows if row.get('test') == 'Vencimiento')
        self.assertEqual((expiry['severity'], expiry['tone']), ('Alto', 'danger'))

    def test_empty_sections_have_no_header(self):
        only = parse_report(report_text([REPORT[4]]))
        rows = grouped(only)
        self.assertEqual([row['header'] for row in rows], [True, False])

    def test_summary_counts_by_severity(self):
        summary = summarize(parse_report(report_text()))
        counts = {item['severity']: item['count'] for item in summary}
        self.assertEqual(counts, {'HIGH': 2, 'MEDIUM': 1, 'LOW': 1, 'OK': 4})
        self.assertEqual([item['severity'] for item in summary], ['HIGH', 'MEDIUM', 'LOW', 'OK'])
        self.assertEqual(summary[0]['tone'], 'danger')
        self.assertEqual(summarize(()), [])


class CommandTest(unittest.TestCase):
    def test_argv(self):
        argv = CommandFactory(Binaries()).tls_scan('example.com:443', ['-S'], '/tmp/x/informe.json')
        self.assertEqual(argv[0], '/usr/bin/testssl')
        self.assertEqual(argv[-2:], ['-S', 'example.com:443'])
        self.assertEqual(argv[argv.index('--jsonfile') + 1], '/tmp/x/informe.json')
        for option in ('--quiet', '--warnings', 'batch', '--color', '0', '--ip', 'one'):
            self.assertIn(option, argv)


class ServiceTest(unittest.TestCase):
    def setUp(self):
        use('es')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runner = FakeRunner()
        (Path(self.tmp.name) / 'tls').mkdir()  # fuera de Linux el servicio no crea la carpeta
        self.service = TlsService(self.runner, CommandFactory(Binaries()), Path(self.tmp.name) / 'tls')
        self.exits = []

    def begin(self, target='example.com', mode='certificate'):
        return self.service.start(target, mode, on_exit=self.exits.append)

    def report_path(self):
        argv = self.runner.starts[-1]
        return Path(argv[argv.index('--jsonfile') + 1])

    def test_start_builds_the_command_for_the_mode(self):
        parsed = self.begin('https://example.com:8443/', 'protocols')
        self.assertEqual(parsed.argument, 'example.com:8443')
        argv = self.runner.starts[0]
        self.assertEqual(argv[-3:], ['-p', '-s', 'example.com:8443'])
        self.assertTrue(self.report_path().parent.is_dir())

    def test_reads_the_report_when_the_process_ends_and_cleans_up(self):
        self.begin()
        report = self.report_path()
        report.write_text(report_text(), encoding='utf-8')
        self.runner.handles[0].finish(0)
        self.assertEqual(self.exits, [0])
        self.assertEqual(len(self.service.findings), 8)
        self.assertFalse(report.parent.exists())

    def test_keeps_what_was_found_when_stopped(self):
        self.begin()
        text = report_text(REPORT[:3])
        self.report_path().write_text(text[:text.rindex('}')], encoding='utf-8')
        self.service.stop()
        self.assertEqual([item.id for item in self.service.findings], ['cert_commonName', 'cert_expirationStatus'])
        self.assertEqual(self.exits, [-15])

    def test_no_report_means_no_findings(self):
        self.begin()
        self.runner.handles[0].finish(1)
        self.assertEqual(self.service.findings, ())

    def test_new_scan_clears_old_findings(self):
        self.begin()
        self.report_path().write_text(report_text(), encoding='utf-8')
        self.runner.handles[0].finish(0)
        self.begin()
        self.assertEqual(self.service.findings, ())

    def test_invalid_input_starts_nothing(self):
        with self.assertRaises(ValidationError):
            self.begin('-oX')
        with self.assertRaises(ValidationError):
            self.begin('example.com', 'otro')
        self.assertEqual(self.runner.starts, [])

    def test_only_one_scan_at_a_time(self):
        self.begin()
        with self.assertRaises(AlreadyRunningError):
            self.begin('example.org')
        self.assertEqual(len(self.runner.starts), 1)

    def test_failed_launch_leaves_no_temporary_folder(self):
        folder = Path(self.tmp.name) / 'work'
        folder.mkdir()
        self.runner.start = mock.Mock(side_effect=OSError('sin permisos'))
        with mock.patch('mulita.services.tls.tempfile.mkdtemp', return_value=str(folder)):
            with self.assertRaises(OSError):
                self.begin()
        self.assertFalse(folder.exists())

    def test_save_writes_a_csv(self):
        findings = parse_report(report_text())
        name = self.service.save(findings, 'analisis')
        self.assertEqual(name, 'analisis.csv')
        lines = (Path(self.tmp.name) / 'tls' / name).read_text(encoding='utf-8').splitlines()
        self.assertEqual(lines[0], 'Sección,Prueba,Severidad,Resultado,CVE')
        self.assertEqual(len(lines), 9)
        self.assertIn('Certificado,Nombre común (CN),Correcto,example.com,', lines)
        self.assertIn('Vulnerabilidades,SWEET32,Bajo,VULNERABLE,CVE-2016-2183', lines)

    def test_save_rejects_empty_duplicates_and_bad_names(self):
        findings = parse_report(report_text())
        with self.assertRaises(ValidationError):
            self.service.save((), 'a')
        self.service.save(findings, 'a')
        with self.assertRaises(ValidationError):
            self.service.save(findings, 'a')
        with self.assertRaises(ValidationError):
            self.service.save(findings, '../fuera')


class ControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        use('es')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runner = FakeRunner()
        (Path(self.tmp.name) / 'tls').mkdir()
        self.service = TlsService(self.runner, CommandFactory(Binaries()), Path(self.tmp.name) / 'tls')
        self.notifier = Notifier()
        self.toasts = []
        self.notifier.notified.connect(lambda *args: self.toasts.append(args))
        self.controller = TlsController(BridgeContext(
            config=None, services=SimpleNamespace(tls=self.service),
            dispatcher=QtDispatcher(), notifier=self.notifier), clock=lambda: '20261027-220000')
        self.console = []
        self.controller.console.appended.connect(self.console.append)

    def pump(self, condition, seconds=3):
        deadline = time.time() + seconds
        while time.time() < deadline:
            self.app.processEvents()
            if condition():
                return
            time.sleep(0.01)
        self.fail('La condicion no se cumplio a tiempo')

    def report_path(self):
        argv = self.runner.starts[-1]
        return Path(argv[argv.index('--jsonfile') + 1])

    def finish(self, code=0, write=True):
        if write:
            self.report_path().write_text(report_text(), encoding='utf-8')
        self.runner.handles[-1].finish(code)
        self.pump(lambda: not self.controller.running)

    def test_modes_are_offered_with_a_default(self):
        modes = json.loads(self.controller.modesJson)
        self.assertEqual(modes['default'], 'certificate')
        self.assertEqual([item['id'] for item in modes['items']],
                         ['certificate', 'protocols', 'vulnerabilities', 'full'])

    def test_scan_shows_grouped_rows_and_summary(self):
        self.assertTrue(self.controller.start('example.com', 'full'))
        self.assertTrue(self.controller.running)
        self.assertEqual(self.controller.target, 'example.com:443')
        self.finish()
        self.assertTrue(self.controller.hasResult)
        rows = json.loads(self.controller.rowsJson)
        self.assertEqual(rows[0], {'header': True, 'title': 'Certificado'})
        summary = {item['severity']: item['count'] for item in json.loads(self.controller.summaryJson)}
        self.assertEqual(summary['HIGH'], 2)
        self.assertEqual(self.toasts, [])

    def test_output_goes_to_the_console_without_carriage_returns(self):
        self.controller.start('example.com', 'certificate')
        self.runner.outputs[-1]('Probando...\r\nlisto\n')
        self.pump(lambda: self.console)
        self.assertEqual(''.join(self.console), 'Probando...\nlisto\n')

    def test_starting_again_clears_the_previous_result(self):
        self.controller.start('example.com', 'certificate')
        self.finish()
        self.assertTrue(self.controller.hasResult)
        self.controller.start('example.org', 'certificate')
        self.assertFalse(self.controller.hasResult)
        self.assertEqual(json.loads(self.controller.rowsJson), [])
        self.assertEqual(self.controller.target, 'example.org:443')

    def test_no_second_start_while_running(self):
        self.assertTrue(self.controller.start('example.com', 'certificate'))
        self.assertFalse(self.controller.start('example.org', 'certificate'))
        self.assertEqual(len(self.runner.starts), 1)

    def test_invalid_target_is_reported(self):
        self.assertFalse(self.controller.start('-oX', 'certificate'))
        self.assertFalse(self.controller.running)
        self.assertEqual(self.toasts[0][0], 'error')
        self.assertEqual(self.runner.starts, [])

    def test_missing_program_explains_the_fix(self):
        self.controller.start('example.com', 'certificate')
        self.finish(MISSING_COMMAND_CODE, write=False)
        self.assertEqual(len(self.toasts), 1)
        self.assertIn('install-lite.sh', self.toasts[0][2])

    def test_failure_shows_the_last_lines(self):
        self.controller.start('example.com', 'certificate')
        self.runner.outputs[-1]('Fatal error: no se pudo conectar a example.com:443\n')
        self.app.processEvents()
        self.finish(1, write=False)
        self.assertEqual(len(self.toasts), 1)
        self.assertIn('no se pudo conectar', self.toasts[0][2])

    def test_clean_exit_without_results_is_reported(self):
        self.controller.start('example.com', 'certificate')
        self.finish(0, write=False)
        self.assertEqual(self.toasts[0][2], 'El análisis no devolvió resultados')

    def test_stopping_keeps_partial_results_and_stays_quiet(self):
        self.controller.start('example.com', 'certificate')
        text = report_text(REPORT[:3])
        self.report_path().write_text(text[:text.rindex('}')], encoding='utf-8')
        self.controller.stop()
        self.pump(lambda: self.controller.hasResult)
        self.assertFalse(self.controller.running)
        self.assertEqual(self.toasts, [])

    def test_save_names_the_file_after_the_server_and_the_time(self):
        self.controller.start('https://Example.com:8443/inicio', 'certificate')
        self.finish()
        self.controller.save()
        self.assertEqual(self.toasts[-1][:1], ('success',))
        self.assertEqual(self.toasts[-1][2], 'tls-Example.com-20261027-220000.csv')
        self.assertTrue((Path(self.tmp.name) / 'tls' / 'tls-Example.com-20261027-220000.csv').is_file())

    def test_save_name_for_ip_addresses(self):
        self.controller.start('[2001:db8::1]:8443', 'certificate')
        self.finish()
        self.controller.save()
        self.assertEqual(self.toasts[-1][2], 'tls-2001-db8-1-20261027-220000.csv')

    def test_save_without_results_is_an_error(self):
        self.controller.save()
        self.assertEqual(self.toasts[-1][0], 'error')
        self.assertEqual(list((Path(self.tmp.name) / 'tls').iterdir()), [])

    def test_save_is_ignored_while_scanning(self):
        self.controller.start('example.com', 'certificate')
        self.controller.save()
        self.assertEqual(self.toasts, [])


if __name__ == '__main__':
    unittest.main()
