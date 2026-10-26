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
from mulita.core.models import PingSummary
from mulita.core.parsers import (cable_connected, parse_discovery_line, parse_interfaces,
                                parse_port_scan, parse_public_address, parse_speed_test,
                                parse_trace, read_ping_line)

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
                         ['/bin/mtr', '8.8.8.8', '-n', '-r', '--csv', '-c', '6'])

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
        self.assertEqual(self.commands.discovery('wlan0'),
                         ['/sbin/netdiscover', '-f', '-P', '-d', '-i', 'wlan0'])
        self.assertEqual(self.commands.speed_test(),
                         ['/bin/speedtest', '--json', '--timeout', '25'])
        self.assertEqual(self.commands.speed_test('192.168.1.20'),
                         ['/bin/speedtest', '--json', '--timeout', '25', '--source', '192.168.1.20'])
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

    def test_interface_name_accepts_linux_devices(self):
        self.assertEqual(validation.interface_name(' wlan0 '), 'wlan0')
        self.assertEqual(validation.interface_name('br-mulita'), 'br-mulita')
        for value in ('', 'eth0;id', '-i', 'a b', '../eth0'):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validation.interface_name(value)

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


class TraceParseTest(unittest.TestCase):

    def test_csv_report_becomes_hops(self):
        text = (
            'Mtr_Version,Start_Time,Status,Host,Hop,Ip,Loss%,Snt, ,Last,Avg,Best,Wrst,StDev,\n'
            '0.95,10,OK,8.8.8.8,1,192.168.1.1,0.0,6,6,1.2,1.3,1.0,1.8,0.3\n'
            '0.95,10,OK,8.8.8.8,2,???,100.0,6,0,0.0,0.0,0.0,0.0,0.0\n'
            '0.95,10,OK,8.8.8.8,3,8.8.8.8,16.7,6,5,20.1,21.0,18.5,25.0,2.1\n'
        )
        hops = parse_trace(text)
        self.assertEqual([(item.hop, item.address, item.loss, item.sent, item.average)
                          for item in hops], [
                              (1, '192.168.1.1', '0.0%', '6', '1.3'),
                              (2, '???', '100.0%', '6', '0.0'),
                              (3, '8.8.8.8', '16.7%', '6', '21.0'),
                          ])
        self.assertEqual(hops[2].best, '18.5')
        self.assertEqual(hops[2].deviation, '2.1')

    def test_report_text_parses_the_same_columns(self):
        text = (
            'HOST: raspberrypi                  Loss%   Snt   Last   Avg  Best  Wrst StDev\n'
            '  1.|-- 192.168.1.1                 0.0%     6    1.2   1.3   1.0   1.8   0.3\n'
            '  2.|-- ???                        100.0     6    0.0   0.0   0.0   0.0   0.0\n'
        )
        hops = parse_trace(text)
        self.assertEqual(hops[0].address, '192.168.1.1')
        self.assertEqual(hops[0].loss, '0.0%')
        self.assertEqual(hops[1].address, '???')
        self.assertEqual(hops[1].loss, '100.0%')
        self.assertEqual(parse_trace('HOST: x\n'), ())

    def test_ping_lines_become_replies_and_a_final_note(self):
        text = """64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=20.1 ms
From 10.0.0.1 icmp_seq=2 Destination Host Unreachable
--- 8.8.8.8 ping statistics ---
2 packets transmitted, 1 received, 50% packet loss, time 1001ms
rtt min/avg/max/mdev = 19.400/20.100/20.100/0.200 ms
"""
        summary = PingSummary()
        replies = []
        for line in text.splitlines():
            reply, summary = read_ping_line(line, summary)
            if reply:
                replies.append(reply)
        self.assertEqual([(item.seq, item.source, item.status) for item in replies],
                         [(1, '8.8.8.8', 'ok'), (2, '10.0.0.1', 'fail')])
        self.assertEqual(summary.target, '8.8.8.8')
        self.assertEqual(summary.transmitted, '2')
        self.assertEqual(summary.received, '1')
        self.assertEqual(summary.loss, '50%')
        self.assertEqual(summary.minimum, '19.400')
        self.assertEqual(summary.deviation, '0.200')

    def test_public_address_keeps_the_network_facts(self):
        info = parse_public_address('''{
            "ip": "181.1.2.3", "success": true, "type": "IPv4",
            "country": "Argentina", "country_code": "AR",
            "region": "Buenos Aires", "city": "Buenos Aires",
            "latitude": -34.6037, "longitude": -58.3816,
            "connection": {"asn": 7303, "org": "Telecom Argentina S.A.",
                           "isp": "Telecom Argentina S.A.", "domain": "telecom.com.ar"},
            "timezone": {"id": "America/Argentina/Buenos_Aires", "utc": "-03:00"}
        }''')
        facts = dict(info.facts())
        self.assertEqual(facts['Dirección'], '181.1.2.3')
        self.assertEqual(facts['Versión'], 'IPv4')
        self.assertEqual(facts['ASN'], 'AS7303')
        self.assertEqual(facts['Organización'], 'Telecom Argentina S.A.')
        self.assertEqual(facts['ISP'], 'Telecom Argentina S.A.')
        self.assertEqual(facts['Dominio'], 'telecom.com.ar')
        self.assertEqual(facts['País'], 'Argentina (AR)')
        self.assertEqual(facts['Ciudad'], 'Buenos Aires')
        self.assertEqual(facts['Coordenadas'], '-34.6037, -58.3816')
        self.assertEqual(facts['Zona horaria'], 'America/Argentina/Buenos_Aires (UTC-03:00)')
        self.assertEqual(parse_public_address('181.1.2.3\n').ip, '181.1.2.3')

    def test_port_scan_report_becomes_rows(self):
        text = """Starting Nmap 7.93
Nmap scan report for router.lan (192.168.0.1)
Host is up (0.0020s latency).
Not shown: 997 closed tcp ports (reset)
PORT     STATE SERVICE
22/tcp   open  ssh
80/tcp   open  http
Nmap scan report for 192.168.0.20
PORT   STATE    SERVICE VERSION
53/udp filtered domain
Nmap done: 2 IP addresses (2 hosts up) scanned in 1.20 seconds
"""
        found = parse_port_scan(text)
        self.assertEqual(
            [(item.host, item.port, item.protocol, item.state, item.service) for item in found],
            [
                ('router.lan (192.168.0.1)', '22', 'tcp', 'open', 'ssh'),
                ('router.lan (192.168.0.1)', '80', 'tcp', 'open', 'http'),
                ('192.168.0.20', '53', 'udp', 'filtered', 'domain'),
            ])

    def test_discovery_line_keeps_ip_mac_and_vendor(self):
        found = parse_discovery_line('192.168.0.1\taa:bb:cc:dd:ee:ff\t3\t060\tCisco Systems\n')
        self.assertEqual((found.ip, found.mac, found.count, found.vendor),
                         ('192.168.0.1', 'AA:BB:CC:DD:EE:FF', '3', 'Cisco Systems'))
        self.assertIsNone(parse_discovery_line('Currently scanning: 192.168.0.0/24'))


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
