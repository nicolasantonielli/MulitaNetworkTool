import csv
import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.fakes import FakeRunner

from mulita.config import Binaries
from mulita.core.commands import CommandFactory
from mulita.core.errors import AlreadyRunningError, CommandFailedError, ValidationError
from mulita.core.models import CommandResult
from mulita.core.servers import KINDS, RANDOM, ServerLog, kind_by_id
from mulita.presentation.i18n import ES, EN, tr, use
from mulita.services.servers import USER_MARK, ServerService

BIN = Binaries()


def ip_json(name='eth1', address='192.168.50.1', prefix=24):
    return json.dumps([{'ifname': name, 'addr_info': [
        {'family': 'inet', 'local': address, 'prefixlen': prefix}]}])


class ScriptedRunner(FakeRunner):
    """Responde segun el comando completo, para distinguir `ip addr` de `ip route`."""

    def __init__(self, replies=None):
        super().__init__()
        self.replies = replies or {}

    def run(self, argv, timeout=None, input_text=None):
        self.runs.append(list(argv))
        self.inputs.append(input_text)
        for needle, result in self.replies.items():
            if needle in ' '.join(argv):
                return result
        return CommandResult(0, 'ok\n')


class CatalogTest(unittest.TestCase):

    def test_every_text_exists_in_both_languages(self):
        keys = set()
        for kind in KINDS:
            keys.update((kind.title, kind.subtitle, kind.hint))
            keys.update(column.title for column in kind.columns)
            for field in kind.fields:
                keys.add(field.label)
                if field.placeholder:
                    keys.add(field.placeholder)
                keys.update(label for _value, label in field.options if label not in ('HTTP', 'HTTPS'))
        self.assertEqual(sorted(key for key in keys if key not in ES), [])
        self.assertEqual(sorted(key for key in keys if key not in EN), [])

    def test_catalog_has_the_seven_services_in_order(self):
        self.assertEqual([kind.id for kind in KINDS],
                         ['iperf', 'tftp', 'sftp', 'web', 'dns', 'dhcp', 'ntp'])

    def test_catalog_is_json_serializable_and_hides_nothing_needed_by_qml(self):
        data = json.loads(json.dumps([kind.to_dict() for kind in KINDS]))
        web = next(item for item in data if item['id'] == 'web')
        https = next(field for field in web['fields'] if field['key'] == 'https_port')
        self.assertEqual(https['when'], {'key': 'mode', 'in': ['https', 'both']})

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(KeyError):
            kind_by_id('ftp')


class ServerLogTest(unittest.TestCase):

    def log(self, kind):
        return ServerLog(kind_by_id(kind), clock=lambda: '10:00:00')

    def test_dns_queries_show_client_and_question(self):
        log = self.log('dns')
        log.feed('dnsmasq: query[A] mulita.test from 192.168.1.20\n'
                 'dnsmasq: config mulita.test is 192.168.50.1\n')
        self.assertEqual(log.rows, [
            {'client': '192.168.1.20', 'event': 'A mulita.test', 'time': '10:00:00'},
            {'client': '', 'event': 'config mulita.test is 192.168.50.1', 'time': '10:00:00'}])

    def test_dhcp_lists_one_lease_per_mac_and_ignores_other_messages(self):
        log = self.log('dhcp')
        log.feed('dnsmasq-dhcp: DHCPDISCOVER(eth1) aa:bb:cc:dd:ee:01\n'
                 'dnsmasq-dhcp: DHCPACK(eth1) 192.168.50.101 AA:BB:CC:DD:EE:01 camara\n'
                 'dnsmasq-dhcp: DHCPACK(eth1) 192.168.50.102 aa:bb:cc:dd:ee:02\n'
                 'dnsmasq-dhcp: DHCPACK(eth1) 192.168.50.105 aa:bb:cc:dd:ee:01 camara\n')
        self.assertEqual([(row['ip'], row['mac'], row['name']) for row in log.rows], [
            ('192.168.50.105', 'aa:bb:cc:dd:ee:01', 'camara'),
            ('192.168.50.102', 'aa:bb:cc:dd:ee:02', '')])
        self.assertEqual(len(log.tail), 4)

    def test_own_servers_use_client_tab_event(self):
        log = self.log('tftp')
        log.feed('10.0.0.5\tRecibido sw1.cfg (120 bytes)\nTFTP escuchando en el puerto 69\n')
        self.assertEqual(log.rows[0]['client'], '10.0.0.5')
        self.assertEqual(log.rows[0]['event'], 'Recibido sw1.cfg (120 bytes)')
        self.assertEqual(log.rows[1]['client'], '')

    def test_iperf_keeps_lines_but_extracts_the_client_and_drops_separators(self):
        log = self.log('iperf')
        log.feed('-----------------------------------------------------------\n'
                 'Accepted connection from 192.168.1.9, port 51514\n'
                 '[  5]   0.00-1.00   sec  11.2 MBytes  94.1 Mbits/sec\n')
        self.assertEqual([row['client'] for row in log.rows], ['192.168.1.9', ''])

    def test_sshd_login_lines_name_the_client(self):
        log = self.log('sftp')
        log.feed('Accepted password for mulita from 192.168.1.9 port 50000 ssh2\n'
                 'Failed password for invalid user admin from 192.168.1.10 port 50001 ssh2\n'
                 'Connection closed by authenticating user mulita 192.168.1.9 port 50000 [preauth]\n')
        self.assertEqual([row['client'] for row in log.rows],
                         ['192.168.1.9', '192.168.1.10', '192.168.1.9'])

    def test_partial_lines_wait_for_the_newline_and_flush_at_exit(self):
        log = self.log('ntp')
        self.assertFalse(log.feed('1.2.3.4\tHora ent'))
        self.assertTrue(log.feed('regada\n'))
        log.feed('9.9.9.9\tultima')
        self.assertTrue(log.flush())
        self.assertEqual(len(log.rows), 2)

    def test_rows_are_capped_and_listed_newest_first(self):
        log = self.log('ntp')
        for number in range(ServerLog.LIMIT + 20):
            log.feed(f'1.1.1.1\tn{number}\n')
        self.assertEqual(len(log.rows), ServerLog.LIMIT)
        self.assertEqual(log.newest_first()[0]['event'], f'n{ServerLog.LIMIT + 19}')


class ServerServiceTest(unittest.TestCase):

    def setUp(self):
        use('es')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.captures = self.root / 'capturas'
        self.captures.mkdir()
        self.runner = ScriptedRunner({
            'addr show dev eth1': CommandResult(0, ip_json()),
            'route show default': CommandResult(0, '[]'),
            'getent': CommandResult(2, ''),
        })
        self.service = self._service(self.runner)

    def _service(self, runner):
        return ServerService(runner, CommandFactory(BIN), self.root / 'servidores',
                             self.root / 'estado', self.captures, posix=True)

    def test_iperf_binds_to_the_chosen_interface(self):
        self.service.start('iperf', {'iface': 'eth1', 'port': '5202', 'once': '1'})
        self.assertEqual(self.runner.starts[-1], [BIN.iperf3, '-s', '-p', '5202', '--forceflush',
                                                  '-B', '192.168.50.1', '-1'])

    def test_iperf_listens_everywhere_by_default(self):
        self.service.start('iperf', {})
        self.assertEqual(self.runner.starts[-1], [BIN.iperf3, '-s', '-p', '5201', '--forceflush'])

    def test_tftp_serves_its_own_folder_and_allows_uploads(self):
        self.service.start('tftp', {'writable': '1'})
        argv = self.runner.starts[-1]
        self.assertEqual(argv[0], BIN.python)
        self.assertEqual(argv[1], '-u')
        self.assertTrue(argv[2].endswith('tftp.py'))
        self.assertIn('--writable', argv)
        self.assertEqual(argv[argv.index('--root') + 1], str(self.root / 'servidores' / 'tftp'))
        self.assertTrue((self.root / 'servidores' / 'tftp').is_dir())

    def test_tftp_without_uploads_has_no_writable_flag(self):
        self.service.start('tftp', {'writable': '0'})
        self.assertNotIn('--writable', self.runner.starts[-1])

    def test_ntp_validates_stratum(self):
        with self.assertRaises(ValidationError):
            self.service.start('ntp', {'stratum': '16'})
        self.service.start('ntp', {'port': '12345', 'stratum': '2'})
        argv = self.runner.starts[-1]
        self.assertEqual(argv[argv.index('--stratum') + 1], '2')
        self.assertEqual(argv[argv.index('--port') + 1], '12345')

    def test_web_http_only_has_no_certificate(self):
        self.service.start('web', {'mode': 'http', 'http_port': '8080', 'share': '0'})
        argv = self.runner.starts[-1]
        self.assertEqual(argv[argv.index('--http-port') + 1], '8080')
        self.assertEqual(argv[argv.index('--https-port') + 1], '0')
        self.assertNotIn('--cert', argv)
        self.assertNotIn('--captures', argv)
        self.assertFalse(any(call[0] == BIN.openssl for call in self.runner.runs))

    def test_web_https_creates_the_certificate_once_outside_shared_folders(self):
        self.service.start('web', {'mode': 'both', 'http_port': '80', 'https_port': '443'})
        make = [call for call in self.runner.runs if call[0] == BIN.openssl]
        self.assertEqual(len(make), 1)
        argv = self.runner.starts[-1]
        self.assertEqual(argv[argv.index('--captures') + 1], str(self.captures))
        self.assertTrue(argv[argv.index('--cert') + 1].startswith(str(self.root / 'estado')))

    def test_web_rejects_equal_ports_and_unknown_mode(self):
        with self.assertRaises(ValidationError):
            self.service.start('web', {'mode': 'both', 'http_port': '8000', 'https_port': '8000'})
        with self.assertRaises(ValidationError):
            self.service.start('web', {'mode': 'ftp'})

    def test_invalid_port_is_rejected_before_launching(self):
        for port in ('', '0', '70000', 'abc'):
            with self.assertRaises(ValidationError):
                self.service.start('iperf', {'port': port})
        self.assertEqual(self.runner.starts, [])

    def test_dns_logs_every_query_and_answers_with_the_interface_address(self):
        self.service.start('dns', {'iface': 'eth1', 'name': 'Mulita.Test', 'upstream': '8.8.8.8'})
        argv = self.runner.starts[-1]
        self.assertEqual(argv[0], BIN.dnsmasq)
        for option in ('--keep-in-foreground', '--conf-file=/dev/null', '--log-queries',
                       '--cache-size=0', '--address=/mulita.test/192.168.50.1',
                       '--listen-address=192.168.50.1', '--bind-interfaces', '--server=8.8.8.8',
                       '--port=53', '--log-facility=-', '--no-resolv'):
            self.assertIn(option, argv)

    def test_dns_needs_an_interface_and_a_valid_name(self):
        with self.assertRaises(ValidationError):
            self.service.start('dns', {'iface': ''})
        with self.assertRaises(ValidationError):
            self.service.start('dns', {'iface': 'eth1', 'name': 'bad name'})
        with self.assertRaises(ValidationError):
            self.service.start('dns', {'iface': 'eth1', 'upstream': 'dns.local'})

    def test_interface_without_address_is_rejected(self):
        runner = ScriptedRunner({'addr show dev eth9': CommandResult(0, '[]')})
        with self.assertRaises(ValidationError):
            self._service(runner).start('iperf', {'iface': 'eth9'})

    def test_dhcp_defaults_use_the_interface_network(self):
        self.service.start('dhcp', {'iface': 'eth1'})
        argv = self.runner.starts[-1]
        self.assertIn('--port=0', argv)
        self.assertIn('--interface=eth1', argv)
        self.assertIn('--dhcp-range=192.168.50.100,192.168.50.150,255.255.255.0,1h', argv)
        self.assertIn('--dhcp-option=option:router,192.168.50.1', argv)
        self.assertIn('--dhcp-option=option:dns-server,192.168.50.1', argv)
        self.assertIn('--log-dhcp', argv)

    def test_dhcp_accepts_custom_range_gateway_dns_and_lease(self):
        self.service.start('dhcp', {'iface': 'eth1', 'first': '192.168.50.10', 'last': '192.168.50.20',
                                    'gateway': '192.168.50.254', 'dns': '1.1.1.1', 'hours': '12'})
        argv = self.runner.starts[-1]
        self.assertIn('--dhcp-range=192.168.50.10,192.168.50.20,255.255.255.0,12h', argv)
        self.assertIn('--dhcp-option=option:router,192.168.50.254', argv)
        self.assertIn('--dhcp-option=option:dns-server,1.1.1.1', argv)

    def test_dhcp_refuses_the_interface_that_carries_the_default_route(self):
        self.runner.replies['route show default'] = CommandResult(
            0, json.dumps([{'dst': 'default', 'gateway': '192.168.50.254', 'dev': 'eth1'}]))
        with self.assertRaises(ValidationError) as caught:
            self.service.start('dhcp', {'iface': 'eth1'})
        self.assertIn('eth1', str(caught.exception))
        self.assertEqual(self.runner.starts, [])

    def test_dhcp_rejects_ranges_outside_the_network_or_over_its_own_address(self):
        for first, last in (('10.0.0.5', '10.0.0.9'), ('192.168.50.1', '192.168.50.9'),
                            ('192.168.50.30', '192.168.50.20'), ('192.168.50.250', '192.168.50.255')):
            with self.assertRaises(ValidationError):
                self.service.start('dhcp', {'iface': 'eth1', 'first': first, 'last': last})
        with self.assertRaises(ValidationError):
            self.service.start('dhcp', {'iface': 'eth1', 'hours': '0'})

    def test_dhcp_refuses_tiny_networks(self):
        self.runner.replies['addr show dev eth1'] = CommandResult(0, ip_json(prefix=30))
        with self.assertRaises(ValidationError):
            self.service.start('dhcp', {'iface': 'eth1'})

    def test_second_start_of_the_same_server_is_rejected_but_others_run_together(self):
        self.service.start('ntp', {})
        self.service.start('iperf', {})
        self.assertTrue(self.service.is_running('ntp'))
        self.assertTrue(self.service.is_running('iperf'))
        with self.assertRaises(AlreadyRunningError):
            self.service.start('ntp', {})

    def test_stop_all_terminates_every_server(self):
        self.service.start('ntp', {})
        self.service.start('iperf', {})
        self.service.stop_all()
        self.assertFalse(self.service.is_running('ntp'))
        self.assertFalse(self.service.is_running('iperf'))

    def test_exit_callback_is_forwarded(self):
        codes = []
        self.service.start('ntp', {}, on_exit=codes.append)
        self.runner.handles[-1].finish(3)
        self.assertEqual(codes, [3])


class SftpTest(unittest.TestCase):

    def setUp(self):
        use('es')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.captures = PurePosixPath('/root/capturas')
        self.runner = ScriptedRunner({'getent': CommandResult(2, '')})
        self.service = ServerService(self.runner, CommandFactory(BIN), self.root / 'servidores',
                                     self.root / 'estado', self.captures, posix=True)
        # Las rutas /root no existen en la prueba: el servicio solo las nombra en la configuracion.
        self.service._make_dir = lambda path, message: None
        (self.root / 'estado' / 'sftp').mkdir(parents=True)
        (self.root / 'estado' / 'sftp' / 'host_ed25519').write_text('key')
        # Solo /run/sshd es del sistema: los archivos de configuración siguen
        # escribiéndose realmente dentro del directorio temporal de la prueba.
        self.sshd_runtime = Mock()
        path_patch = patch('mulita.services.servers.Path', side_effect=lambda value:
                           self.sshd_runtime if value == '/run/sshd' else Path(value))
        path_patch.start()
        self.addCleanup(path_patch.stop)

    def config(self):
        return (self.root / 'estado' / 'sftp' / 'sshd_config').read_text()

    def test_creates_a_temporary_user_with_its_password_on_stdin(self):
        self.service.start('sftp', {'user': 'tecnico', 'password': 'Clave123', 'port': '2200'})
        commands = [call[0] for call in self.runner.runs]
        self.assertIn(BIN.useradd, commands)
        add = next(call for call in self.runner.runs if call[0] == BIN.useradd)
        self.assertEqual(add[-2:], [USER_MARK, 'tecnico'])
        index = self.runner.runs.index([BIN.chpasswd])
        self.assertEqual(self.runner.inputs[index], 'tecnico:Clave123\n')
        self.assertFalse(any('Clave123' in ' '.join(call) for call in self.runner.runs))
        self.assertEqual(self.runner.starts[-1][:3], [BIN.sshd, '-D', '-e'])
        self.sshd_runtime.mkdir.assert_called_once_with(mode=0o755, parents=True, exist_ok=True)

    def test_config_confines_the_user_to_the_captures_folder(self):
        self.service.start('sftp', {'user': 'tecnico', 'password': 'Clave123', 'port': '2200',
                                    'iface': '', 'writable': '1'})
        text = self.config()
        for line in ('Port 2200', 'AllowUsers tecnico', 'Match User tecnico',
                     '    ChrootDirectory /root/capturas', '    ForceCommand internal-sftp',
                     'PermitRootLogin no', 'AllowTcpForwarding no', 'PermitTTY no'):
            self.assertIn(line, text.splitlines())
        self.assertNotIn('ListenAddress', text)

    def test_read_only_mode_adds_the_flag(self):
        self.service.start('sftp', {'user': 'tecnico', 'password': 'Clave123', 'writable': '0'})
        self.assertIn('    ForceCommand internal-sftp -R', self.config().splitlines())

    def test_stop_removes_the_user_and_hands_uploads_back_to_root(self):
        self.service.start('sftp', {'user': 'tecnico', 'password': 'Clave123'})
        self.service.stop('sftp')
        self.assertEqual(self.runner.runs[-2],
                         [BIN.chown, '-R', 'root:root', '/root/capturas/respaldos'])
        self.assertEqual(self.runner.runs[-1], [BIN.userdel, '--force', 'tecnico'])

    def test_cleanup_runs_once_when_the_process_exits_after_stop(self):
        self.service.start('sftp', {'user': 'tecnico', 'password': 'Clave123'})
        self.service.stop('sftp')
        before = len(self.runner.runs)
        self.runner.handles[-1].finish(0)
        self.assertEqual(len(self.runner.runs), before)

    def test_user_that_belongs_to_the_system_is_never_touched(self):
        self.runner.replies['getent'] = CommandResult(0, 'pi:x:1000:1000:Pi,,,:/home/pi:/bin/bash\n')
        with self.assertRaises(ValidationError):
            self.service.start('sftp', {'user': 'pi', 'password': 'Clave123'})
        self.assertFalse(any(call[0] in (BIN.useradd, BIN.userdel) for call in self.runner.runs))

    def test_leftover_user_of_a_previous_run_is_reused(self):
        self.runner.replies['getent'] = CommandResult(0, f'tecnico:x:998:998:{USER_MARK}:/:/usr/sbin/nologin\n')
        self.service.start('sftp', {'user': 'tecnico', 'password': 'Clave123'})
        self.assertFalse(any(call[0] == BIN.useradd for call in self.runner.runs))

    def test_failed_preparation_removes_the_user_it_created(self):
        self.runner.replies['chpasswd'] = CommandResult(1, '', 'chpasswd: error')
        with self.assertRaises(CommandFailedError):
            self.service.start('sftp', {'user': 'tecnico', 'password': 'Clave123'})
        self.assertEqual(self.runner.runs[-1], [BIN.userdel, '--force', 'tecnico'])
        self.assertEqual(self.runner.starts, [])

    def test_weak_or_odd_credentials_are_rejected(self):
        for user, password in (('root', 'Clave123'), ('Mal Nombre', 'Clave123'),
                               ('tecnico', 'corta'), ('tecnico', ' conespacio '), ('', 'Clave123')):
            with self.assertRaises(ValidationError):
                self.service.start('sftp', {'user': user, 'password': password})
        self.assertFalse(any(call[0] == BIN.useradd for call in self.runner.runs))


class SaveLogTest(unittest.TestCase):

    def setUp(self):
        use('es')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.service = ServerService(FakeRunner(), CommandFactory(BIN), self.root / 'servidores',
                                     self.root / 'estado', self.root / 'capturas', posix=True)

    def test_saves_the_columns_of_the_server(self):
        name = self.service.save('dns', [
            {'time': '10:00:00', 'client': '192.168.1.20', 'event': 'A mulita.test'}], 'consultas')
        self.assertEqual(name, 'consultas.csv')
        with (self.root / 'servidores' / 'registros' / name).open(encoding='utf-8') as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(rows, [[tr('srvTime'), tr('srvClient'), tr('srvEvent')],
                                ['10:00:00', '192.168.1.20', 'A mulita.test']])

    def test_refuses_empty_logs_bad_names_and_overwrites(self):
        with self.assertRaises(ValidationError):
            self.service.save('dns', [], 'consultas')
        row = [{'time': '10:00:00', 'client': 'x', 'event': 'y'}]
        with self.assertRaises(ValidationError):
            self.service.save('dns', row, '../fuga')
        self.service.save('dns', row, 'consultas')
        with self.assertRaises(ValidationError):
            self.service.save('dns', row, 'consultas')


if __name__ == '__main__':
    unittest.main()
