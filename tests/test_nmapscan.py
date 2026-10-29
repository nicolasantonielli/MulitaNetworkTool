import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tests.fakes import FakeRunner

from mulita.config import Binaries
from mulita.core.commands import CommandFactory
from mulita.core.errors import ValidationError
from mulita.core.models import MISSING_COMMAND_CODE, CommandResult
from mulita.core.nmapscan import (Progress, compare_scans, compile_scan, parse_xml,
                                  script_kind, update_progress)
from mulita.presentation.i18n import use
from mulita.services.nmapscan import NmapScanService

TODAY = date(2026, 10, 28)
XML = """<?xml version="1.0"?>
<nmaprun scanner="nmap" args="nmap" version="7.94">
<host>
  <status state="up" reason="arp-response"/>
  <address addr="192.168.1.10" addrtype="ipv4"/>
  <address addr="AA:BB:CC:DD:EE:FF" addrtype="mac" vendor="Cisco"/>
  <hostnames><hostname name="camara.local" type="PTR"/></hostnames>
  <ports>
    <port protocol="tcp" portid="445">
      <state state="open" reason="syn-ack"/>
      <service name="microsoft-ds" product="Samba" version="4.15"/>
      <script id="smb-protocols" output="NT LM 0.12 (SMBv1)"/>
    </port>
    <port protocol="udp" portid="53">
      <state state="open|filtered" reason="no-response"/>
      <service name="domain"/>
    </port>
    <port protocol="tcp" portid="443">
      <state state="open" reason="syn-ack"/>
      <service name="https" product="nginx" version="1.18"/>
      <script id="ssl-cert" output="Subject: commonName=camara.local&#xa;Issuer: commonName=R3&#xa;Subject Alternative Name: DNS:camara.local&#xa;Not valid before: 2026-01-15T00:00:00&#xa;Not valid after: 2026-11-02T23:59:59&#xa;SHA-256: AB"/>
      <script id="ssl-heartbleed" output="VULNERABLE"/>
    </port>
  </ports>
  <os><osmatch name="Linux 5.4" accuracy="96"/></os>
  <hostscript><script id="smb-security-mode" output="message signing enabled but not required"/></hostscript>
</host>
<host>
  <status state="down" reason="no-response"/>
  <address addr="192.168.1.11" addrtype="ipv4"/>
</host>
<runstats><finished exit="success"/></runstats>
</nmaprun>
"""


def options(**extra):
    data = {'profile': 'tcp-fast', 'targets': '10.0.0.5', 'ports': '', 'udp': 'top20',
            'interface': '', 'exclude': '', 'noDns': False, 'noDiscovery': False,
            'timing': 'T3', 'sni': '', 'scripts': [], 'custom': ''}
    data.update(extra)
    return data


def args_of(data, **kwargs):
    return compile_scan(data, **kwargs).args


class CompileTest(unittest.TestCase):
    def setUp(self):
        use('es')

    def test_profiles_match_the_requested_commands(self):
        cases = {
            'discover': ['-v', '--stats-every', '5s', '-sn', '-n', '10.0.0.5'],
            'tcp-fast': ['-v', '--stats-every', '5s', '-sT', '-T3', '--top-ports', '100', '--reason', '10.0.0.5'],
            'tcp-standard': ['-v', '--stats-every', '5s', '-sT', '-T3', '--top-ports', '1000', '--reason', '10.0.0.5'],
            'tcp-all': ['-v', '--stats-every', '5s', '-sT', '-T3', '-p-', '--reason', '10.0.0.5'],
            'syn': ['-v', '--stats-every', '5s', '-sS', '-T3', '--top-ports', '1000', '--reason', '10.0.0.5'],
            'os': ['-v', '--stats-every', '5s', '-sS', '-O', '--osscan-limit', '-T3', '10.0.0.5'],
            'smb': ['-v', '--stats-every', '5s', '-sT', '-p', '139,445', '--script',
                    'smb-protocols,smb-security-mode,smb2-security-mode', '10.0.0.5'],
        }
        for profile, expected in cases.items():
            with self.subTest(profile=profile):
                compiled = compile_scan(options(profile=profile, interface='eth0') if profile == 'arp' else options(profile=profile))
                self.assertEqual(compiled.args, expected)
                self.assertTrue(compiled.command.startswith('nmap '))
                self.assertNotIn('/usr/bin', compiled.command)

    def test_arp_uses_the_interface_and_states_the_limit(self):
        compiled = compile_scan(options(profile='arp', interface='eth0'))
        self.assertEqual(compiled.args, ['-v', '--stats-every', '5s', '-sn', '-PR', '-n', '-e', 'eth0', '10.0.0.5'])
        with self.assertRaises(ValidationError):
            compile_scan(options(profile='arp'))

    def test_targets_ports_and_modifiers(self):
        compiled = compile_scan(options(
            profile='ports', targets='10.0.0.5 ejemplo.com 192.168.1.0/24 192.168.1.10-20',
            ports='22,80,443', noDns=True, noDiscovery=True, timing='T4',
            interface='eth0', exclude='10.0.0.1'))
        self.assertEqual(compiled.args, [
            '-v', '--stats-every', '5s', '-sT', '-T4', '-p', '22,80,443', '--reason',
            '-n', '-Pn', '-e', 'eth0', '--exclude', '10.0.0.1',
            '10.0.0.5', 'ejemplo.com', '192.168.1.0/24', '192.168.1.10-20'])
        self.assertTrue(any('subred' in note for note in compiled.notes))

    def test_dns_flag_is_not_repeated(self):
        compiled = compile_scan(options(profile='discover', noDns=True))
        self.assertEqual(compiled.args.count('-n'), 1)

    def test_default_timing_is_not_added_to_profiles_without_it(self):
        compiled = compile_scan(options(profile='http', ports='80,443'))
        self.assertNotIn('-T3', compiled.args)
        changed = compile_scan(options(profile='http', ports='80,443', timing='T2'))
        self.assertIn('-T2', changed.args)

    def test_versions_use_previous_ports_or_the_top_1000(self):
        self.assertIn('--top-ports', args_of(options(profile='versions', ports='*')))
        self.assertEqual(args_of(options(profile='versions', ports='*'))[args_of(options(profile='versions', ports='*')).index('--top-ports') + 1], '1000')
        chosen = args_of(options(profile='versions', ports='22,80'))
        self.assertIn('-p', chosen)
        self.assertIn('22,80', chosen)

    def test_udp_choices_keep_open_filtered_wording_in_the_hint_path(self):
        self.assertIn('20', args_of(options(profile='udp')))
        hundred = args_of(options(profile='udp', udp='top100'))
        self.assertEqual(hundred[hundred.index('--top-ports') + 1], '100')
        own = args_of(options(profile='udp', udp='custom', ports='53,123'))
        self.assertIn('53,123', own)

    def test_tls_sni_and_checks_are_explicit(self):
        cert = args_of(options(profile='tls-cert', ports='443', sni='camara.local'))
        self.assertIn('ssl-cert', cert)
        self.assertIn('tls.servername=camara.local', cert)
        checks = args_of(options(profile='checks', ports='445', scripts=['smb-vuln-ms17-010']))
        self.assertIn('--script', checks)
        self.assertIn('smb-vuln-ms17-010', checks)
        self.assertNotIn('vuln', checks)
        with self.assertRaises(ValidationError):
            compile_scan(options(profile='checks', scripts=[]))
        with self.assertRaises(ValidationError):
            compile_scan(options(profile='checks', scripts=['vuln']))

    def test_custom_line_does_not_duplicate_the_target_and_strips_only_nmap(self):
        compiled = compile_scan(options(profile='custom', custom='nmap -sV -p 22,80,443 --reason 192.168.1.10',
                                        targets='10.0.0.5'))
        self.assertEqual(compiled.args[-1], '192.168.1.10')
        self.assertNotIn('10.0.0.5', compiled.args)
        self.assertNotIn('nmap', compiled.args)
        self.assertTrue(any('línea' in note for note in compiled.notes))
        added = compile_scan(options(profile='custom', custom='-sV -p 22', targets='10.0.0.8'))
        self.assertEqual(added.args[-1], '10.0.0.8')
        self.assertTrue(any('campo' in note for note in added.notes))

    def test_custom_output_options_and_shell_characters_are_rejected(self):
        for line in ('-sV -oX informe.xml 10.0.0.5', '-oN out 10.0.0.5', '--append-output -sV 10.0.0.5',
                     'nmap -sT 10.0.0.5'):
            if line.endswith('10.0.0.5') and '-o' not in line and 'append' not in line:
                continue
            with self.subTest(line=line):
                with self.assertRaises(ValidationError):
                    compile_scan(options(profile='custom', custom=line))
        with self.assertRaises(ValidationError):
            compile_scan(options(targets='10.0.0.5; id'))
        with self.assertRaises(ValidationError):
            compile_scan(options(targets='-oX'))
        with self.assertRaises(ValidationError):
            compile_scan(options(profile='custom', custom='-sV 10.0.0.5;id'))
        listed = compile_scan(options(profile='custom', custom='-iL @escaneo/lista.txt', targets=''),
                              resolve_file=lambda value: 'C:/lista.txt' if value.startswith('@') else None)
        self.assertEqual(listed.target_count, 0)
        self.assertIn('-iL', listed.args)
        self.assertIsInstance(listed.args, list)

    def test_custom_option_values_remain_attached_to_their_options(self):
        for flag, value in (('--scan-delay', '100ms'), ('--max-scan-delay', '1s'),
                            ('--min-hostgroup', '8'), ('--mtu', '24')):
            with self.subTest(flag=flag):
                compiled = compile_scan(options(profile='custom',
                    custom=f'{flag} {value} -sV 192.168.1.10'))
                at = compiled.args.index(flag)
                self.assertEqual(compiled.args[at:at + 3], [flag, value, '-sV'])
                self.assertEqual(compiled.target_count, 1)
        attached = compile_scan(options(profile='custom',
            custom='--scan-delay=100ms --stats-every=10s -sV 192.168.1.10'))
        self.assertIn('--scan-delay=100ms', attached.args)
        self.assertNotIn('--stats-every', attached.args)

    def test_custom_scripts_are_collected_for_preflight(self):
        for flag in ('--script ssl-cert,ssh-hostkey', '--script=ssl-cert,ssh-hostkey'):
            with self.subTest(flag=flag):
                compiled = compile_scan(options(profile='custom', custom=f'{flag} 10.0.0.5'))
                self.assertEqual(compiled.scripts, ('ssl-cert', 'ssh-hostkey'))
        for flag in ('-sC', '-A'):
            self.assertEqual(compile_scan(options(profile='custom', custom=flag)).scripts, ('default',))

    def test_custom_equals_file_option_resolves_without_consuming_next_flag(self):
        compiled = compile_scan(options(profile='custom',
            custom='--excludefile=@escaneo/lista.txt -sV 10.0.0.5'),
            resolve_file=lambda _value: '/tmp/lista.txt')
        self.assertIn('--excludefile=/tmp/lista.txt', compiled.args)
        self.assertIn('-sV', compiled.args)

    def test_custom_file_token_is_resolved_for_the_process_and_hidden_in_the_preview(self):
        def resolve(value):
            return 'C:/capturas/escaneo/lista.txt' if value == '@escaneo/lista.txt' else None

        compiled = compile_scan(options(profile='custom', custom='-iL @escaneo/lista.txt', targets=''),
                                resolve_file=resolve)
        self.assertIn('@escaneo/lista.txt', compiled.command)
        self.assertNotIn('C:/capturas', compiled.command)
        self.assertIn('C:/capturas/escaneo/lista.txt', compiled.args)
        with self.assertRaises(ValidationError):
            compile_scan(options(profile='custom', custom='-iL @escaneo/falta.txt'), resolve_file=resolve)
        with self.assertRaises(ValidationError):
            compile_scan(options(profile='custom', custom='--script vuln', targets='10.0.0.5'))

    def test_ipv6_and_several_targets(self):
        compiled = compile_scan(options(targets='2001:db8::1 ejemplo.com'))
        self.assertEqual(compiled.args[-2:], ['2001:db8::1', 'ejemplo.com'])


class XmlTest(unittest.TestCase):
    def setUp(self):
        use('es')

    def test_reads_hosts_even_without_open_ports_and_keeps_ambiguous_states(self):
        document = parse_xml(XML, TODAY)
        self.assertFalse(document.partial)
        self.assertEqual([host['ip'] for host in document.hosts], ['192.168.1.10', '192.168.1.11'])
        self.assertEqual(document.hosts[1]['state'], 'down')
        self.assertEqual(document.hosts[1]['ports'], [])
        ports = {item['port']: item for item in document.hosts[0]['ports']}
        self.assertEqual(ports['53']['state'], 'open|filtered')
        self.assertEqual(ports['445']['service'], 'microsoft-ds')
        self.assertEqual(ports['445']['version'], '4.15')
        self.assertEqual(document.hosts[0]['mac'], 'AA:BB:CC:DD:EE:FF')
        self.assertEqual(document.hosts[0]['vendor'], 'Cisco')
        self.assertIn('Linux 5.4 (96%)', document.hosts[0]['os'])

    def test_script_kinds_notes_and_certificate_days(self):
        host = parse_xml(XML, TODAY).hosts[0]
        smb = host['ports'][0]['scripts'][0]
        self.assertEqual(smb['note'], 'nmapSmbV1')
        heart = host['ports'][2]['scripts'][1]
        self.assertEqual(heart['kind'], 'vulnerable')
        cert = host['ports'][2]['scripts'][0]
        self.assertEqual(cert['days'], 5)
        self.assertEqual(host['scripts'][0]['note'], 'nmapSmbSignOptional')
        self.assertEqual(script_kind('NOT VULNERABLE'), 'ok')
        self.assertEqual(script_kind('ERROR: no se pudo conectar'), 'error')
        self.assertEqual(script_kind('Could not negotiate'), 'inconclusive')
        self.assertEqual(script_kind('http title'), 'info')

    def test_a_cut_report_keeps_the_complete_hosts(self):
        cut = XML[:XML.index('</host>') + len('</host>')] + '<host><status state="up"'
        document = parse_xml(cut, TODAY)
        self.assertTrue(document.partial)
        self.assertEqual(len(document.hosts), 1)
        self.assertEqual(parse_xml('no es xml').hosts, ())
        self.assertTrue(parse_xml('no es xml').partial)

    def test_compare_ignores_open_filtered(self):
        before = [{'ip': '10.0.0.1', 'state': 'up', 'ports': [
            {'port': '22', 'protocol': 'tcp', 'state': 'open', 'service': 'ssh', 'product': 'OpenSSH', 'version': '7'}]}]
        after = [{'ip': '10.0.0.1', 'state': 'up', 'ports': [
            {'port': '22', 'protocol': 'tcp', 'state': 'open', 'service': 'ssh', 'product': 'OpenSSH', 'version': '8'},
            {'port': '80', 'protocol': 'tcp', 'state': 'open', 'service': 'http', 'product': '', 'version': ''},
            {'port': '53', 'protocol': 'udp', 'state': 'open|filtered', 'service': 'domain', 'product': '', 'version': ''}]},
            {'ip': '10.0.0.2', 'state': 'up', 'ports': []}]
        found = compare_scans(before, after)
        self.assertEqual(found['newHosts'], ['10.0.0.2'])
        self.assertEqual(found['newPorts'], ['10.0.0.1 tcp/80'])
        self.assertEqual(found['gonePorts'], [])
        self.assertIn('OpenSSH 7', found['changes'][0])
        self.assertIn('OpenSSH 8', found['changes'][0])

    def test_progress_is_copied_only_when_nmap_reports_it(self):
        progress = Progress()
        self.assertFalse(update_progress(progress, 'Iniciando\n'))
        self.assertEqual(progress.percent, '')
        update_progress(progress, 'Stats: 0:01:05 elapsed; 0 hosts completed (1 up), 1 undergoing SYN Stealth Scan\n')
        update_progress(progress, 'SYN Stealth Scan Timing: About 12.50% done; ETC: 21:05 (0:00:35 remaining)\n')
        self.assertEqual((progress.elapsed, progress.phase, progress.percent, progress.remaining),
                         ('0:01:05', 'SYN Stealth Scan', '12.50', '0:00:35'))
        self.assertTrue(progress.phase_only)


class ServiceTest(unittest.TestCase):
    def setUp(self):
        use('es')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.runner = FakeRunner({' /usr/bin/nmap': CommandResult(0, 'Nmap version 7.94\n')})
        # FakeRunner busca por argv[0]. El binario de las pruebas es /bin/nmap.
        self.runner.results['/bin/nmap'] = CommandResult(0, 'Nmap version 7.94\n')
        self.service = NmapScanService(self.runner, CommandFactory(Binaries()), root / 'nmap', root / 'estado', root / 'capturas')

    def test_a_run_keeps_xml_text_errors_and_csv_apart(self):
        prepared = self.service.prepare(options())
        self.service.launch(prepared, on_output=lambda _text: None, on_exit=lambda _code: None)
        argv = self.runner.starts[-1]
        self.assertEqual(argv[0], '/bin/nmap')
        self.assertTrue(self.runner.groups[-1])
        xml = Path(argv[argv.index('-oX') + 1])
        normal = Path(argv[argv.index('-oN') + 1])
        self.assertNotEqual(xml, normal)
        xml.write_text(XML, encoding='utf-8')
        self.runner.outputs[-1]('Stats: 0:00:05 elapsed; 0 hosts completed (1 up), 1 undergoing Connect Scan\n')
        self.runner.errors[-1]('aviso de nmap\n')
        self.runner.handles[-1].finish(0)
        folder = prepared.folder
        self.assertTrue((folder / 'informe.xml').is_file())
        self.assertIn('-oN', argv)
        self.assertNotEqual(xml, normal)
        self.assertIn('Connect Scan', (folder / 'progreso.txt').read_text(encoding='utf-8'))
        self.assertIn('aviso', (folder / 'errores.txt').read_text(encoding='utf-8'))
        self.assertNotIn('<nmaprun', (folder / 'progreso.txt').read_text(encoding='utf-8'))
        csv_text = (folder / 'puertos.csv').read_text(encoding='utf-8')
        self.assertIn('Abierto o filtrado', csv_text)
        self.assertIn('192.168.1.11', csv_text)
        meta = json.loads((folder / 'meta.json').read_text(encoding='utf-8'))
        self.assertEqual(meta['status'], 'ok')
        self.assertEqual(meta['nmapVersion'], '7.94')
        self.assertEqual(self.service.outcome.open_ports, '443,445')
        self.assertEqual(len(self.service.outcome.hosts), 2)

    def test_cancel_marks_the_report_and_keeps_a_partial_reading(self):
        prepared = self.service.prepare(options(profile='discover'))
        self.service.launch(prepared)
        argv = self.runner.starts[-1]
        xml = Path(argv[argv.index('-oX') + 1])
        xml.write_text(XML[:XML.index('</host>') + len('</host>')] + '<host><status state="up"', encoding='utf-8')
        self.service.request_cancel()
        self.service.stop()
        self.assertEqual(self.service.outcome.status, 'cancelled')
        self.assertTrue(self.service.outcome.partial)
        self.assertEqual(len(self.service.outcome.hosts), 1)
        meta = json.loads((prepared.folder / 'meta.json').read_text(encoding='utf-8'))
        self.assertEqual(meta['status'], 'cancelled')

    def test_missing_script_is_reported_before_launch(self):
        self.runner.run = self._help
        from mulita.core.errors import CommandFailedError
        with self.assertRaises(CommandFailedError) as caught:
            self.service.prepare(options(profile='checks', ports='443', scripts=['ssl-heartbleed']))
        self.assertIn('ssl-heartbleed', str(caught.exception))
        self.assertEqual(self.runner.starts, [])

    def test_missing_custom_script_is_reported_before_launch(self):
        from mulita.core.errors import CommandFailedError
        self.runner.run = self._help
        for flag in ('--script ssl-cert', '--script=ssl-cert'):
            with self.subTest(flag=flag):
                with self.assertRaises(CommandFailedError) as caught:
                    self.service.prepare(options(profile='custom', custom=f'{flag} 10.0.0.5'))
                self.assertIn('ssl-cert', str(caught.exception))
        self.assertEqual(self.runner.starts, [])

    def test_logs_are_persisted_during_scan_with_bounded_memory(self):
        prepared = self.service.prepare(options())
        self.service.launch(prepared)
        self.runner.errors[-1]('requires root\n')
        for number in range(100):
            self.runner.outputs[-1](f'line {number}\n')
        self.runner.outputs[-1]('x' * 10000 + '\n')
        # Aún no se notificó la salida del proceso: los registros ya existen.
        progress = (prepared.folder / 'progreso.txt').read_text(encoding='utf-8')
        self.assertIn('line 0\n', progress)
        self.assertIn('line 99\n', progress)
        self.assertIn('x' * 10000, progress)
        self.assertEqual((prepared.folder / 'errores.txt').read_text(encoding='utf-8'), 'requires root\n')
        self.assertLessEqual(len(self.service._tail), 8)
        self.assertTrue(all(len(line) <= 2048 for line in self.service._tail))
        self.runner.handles[-1].finish(1)
        self.assertTrue(self.service.outcome.privilege)
        self.assertEqual((prepared.folder / 'progreso.txt').read_text(encoding='utf-8'), progress)

    def _help(self, argv, timeout=None, input_text=None):
        self.runner.runs.append(list(argv))
        if '--script-help' in argv:
            return CommandResult(1, '', 'did not match a category')
        return CommandResult(0, 'Nmap version 7.94\n')

    def test_missing_nmap(self):
        self.runner.results['/bin/nmap'] = CommandResult(MISSING_COMMAND_CODE, '', 'falta')
        from mulita.core.errors import CommandFailedError
        with self.assertRaises(CommandFailedError):
            self.service.prepare(options())

    def test_user_profiles_can_be_saved_duplicated_and_deleted(self):
        saved = self.service.save_user('', 'Oficina', 'SSH de la oficina', '-sV -p 22')
        self.assertEqual(saved['id'], 'user-1')
        copy = self.service.duplicate_user('user-1')
        self.assertEqual(copy['name'], 'Oficina copia')
        compiled = compile_scan(options(profile='user-2', targets='10.0.0.9'),
                                {item['id']: item for item in self.service.users()})
        self.assertEqual(compiled.args[-1], '10.0.0.9')
        self.assertIn('-sV', compiled.args)
        with self.assertRaises(ValidationError):
            self.service.save_user('', 'Otro', '', '-oX secreto.xml 10.0.0.1')
        self.service.delete_user('user-1')
        self.assertEqual([item['id'] for item in self.service.users()], ['user-2'])

    def test_history_and_compare_reload_the_files(self):
        prepared = self.service.prepare(options())
        self.service.launch(prepared)
        Path(self.runner.starts[-1][self.runner.starts[-1].index('-oX') + 1]).write_text(XML, encoding='utf-8')
        self.runner.handles[-1].finish(0)
        second = self.service.prepare(options(targets='10.0.0.6'))
        self.service.launch(second)
        Path(self.runner.starts[-1][self.runner.starts[-1].index('-oX') + 1]).write_text(
            XML.replace('192.168.1.10', '10.0.0.6'), encoding='utf-8')
        self.runner.handles[-1].finish(0)
        runs = self.service.history()
        self.assertEqual(len(runs), 2)
        self.assertNotIn('argv', runs[0])
        first = next(item for item in runs if item['targets'] == '10.0.0.5')
        second = next(item for item in runs if item['targets'] == '10.0.0.6')
        found = self.service.compare(first['id'], second['id'], TODAY)
        self.assertIn('10.0.0.6', found['newHosts'])
        self.assertIn('192.168.1.10', found['goneHosts'])


if __name__ == '__main__':
    unittest.main()
