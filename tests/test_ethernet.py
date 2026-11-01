import unittest
import json

from mulita.config import Binaries
from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.models import AddressMode, CommandResult, EthernetConfig
from mulita.core.parsers import (parse_connection_name, parse_default_gateway,
                                parse_interface_ipv4, parse_nmcli_device_ipv4,
                                parse_nmcli_ipv4)
from mulita.services.ethernet import EthernetService

NM = '/usr/bin/nmcli'
LEASE = '''IP4.ADDRESS[1]:192.168.0.45/24
IP4.GATEWAY:192.168.0.1
IP4.DNS[1]:192.168.0.1
IP4.DNS[2]:8.8.8.8
'''
ADDR = '''[{"ifname":"eth0","addr_info":[
 {"family":"inet","local":"192.168.0.45","prefixlen":24},
 {"family":"inet6","local":"fe80::1"}]}]'''
ROUTE = '[{"dst":"default","gateway":"192.168.0.1","dev":"eth0"}]'


def lease_results(nmcli: str = LEASE) -> list[CommandResult]:
    return [CommandResult(0, nmcli), CommandResult(0, ADDR), CommandResult(0, ROUTE)]


class Script:
    def __init__(self, replies):
        self.replies = list(replies)
        self.runs = []

    def run(self, argv, timeout=None):
        self.runs.append(list(argv))
        return self.replies.pop(0)


def service(script: Script) -> EthernetService:
    return EthernetService(script, CommandFactory(Binaries()), 'eth0', 'mulita-interna')


class EthernetRulesTest(unittest.TestCase):

    def test_netmask_and_prefix(self):
        self.assertEqual(validation.netmask_prefix('255.255.255.0'), 24)
        self.assertEqual(validation.netmask_prefix('/16'), 16)
        self.assertEqual(validation.netmask_prefix('24'), 24)

    def test_static_normalizes_address(self):
        config = validation.static_ethernet('192.168.1.10', '255.255.255.0', '192.168.1.1', '8.8.8.8')
        self.assertEqual(config, EthernetConfig(AddressMode.ESTATICA, '192.168.1.10', 24, '192.168.1.1', '8.8.8.8'))

    def test_static_rejects_bad_values(self):
        for args in (
            ('10.0.0.0', '255.255.255.0', '10.0.0.1', ''),
            ('10.0.0.5', '255.255.255.0', '10.0.1.1', ''),
            ('10.0.0.5', '255.255.255.0', '10.0.0.5', ''),
            ('no-es-ip', '255.255.255.0', '', ''),
            ('10.0.0.5', '255.0.255.0', '', ''),
        ):
            with self.subTest(args=args):
                with self.assertRaises(ValidationError):
                    validation.static_ethernet(*args)

    def test_parse_dhcp_and_static(self):
        self.assertIsNone(parse_connection_name('--\n'))
        self.assertEqual(parse_connection_name('Wired connection 1\n'), 'Wired connection 1')
        self.assertEqual(parse_nmcli_ipv4('auto\n\n\n\n').mode, AddressMode.DHCP)
        config = parse_nmcli_ipv4('manual\n192.168.1.10/24\n192.168.1.1\n8.8.8.8\n')
        self.assertEqual(config, EthernetConfig(AddressMode.ESTATICA, '192.168.1.10', 24, '192.168.1.1', '8.8.8.8'))
        leased = parse_nmcli_device_ipv4(LEASE)
        self.assertEqual(leased, EthernetConfig(AddressMode.DHCP, '192.168.0.45', 24, '192.168.0.1', '192.168.0.1, 8.8.8.8'))
        self.assertEqual(parse_nmcli_device_ipv4('').address, '')
        packed = parse_nmcli_device_ipv4(
            'IP4.ADDRESS[1]:ip = 192.168.0.45/24, gw = 192.168.0.1\nIP4.DNS[1]:8.8.8.8')
        self.assertEqual((packed.address, packed.prefix, packed.gateway, packed.dns),
                         ('192.168.0.45', 24, '192.168.0.1', '8.8.8.8'))
        one_line = parse_nmcli_device_ipv4(
            'IP4.ADDRESS[1]:192.168.0.45/24:IP4.GATEWAY:192.168.0.1:IP4.DNS[1]:8.8.8.8')
        self.assertEqual((one_line.address, one_line.gateway, one_line.dns),
                         ('192.168.0.45', '192.168.0.1', '8.8.8.8'))
        self.assertEqual(parse_interface_ipv4(ADDR), ('192.168.0.45', 24))
        self.assertEqual(parse_default_gateway(ROUTE), '192.168.0.1')


class EthernetCommandsTest(unittest.TestCase):

    def setUp(self):
        self.commands = CommandFactory(Binaries())

    def test_dhcp_and_static_commands(self):
        self.assertEqual(self.commands.set_dhcp('lan'),
                         [NM, 'connection', 'modify', 'lan', 'ipv4.method', 'auto',
                          'ipv4.addresses', '', 'ipv4.gateway', '', 'ipv4.dns', ''])
        self.assertEqual(self.commands.set_static('lan', '192.168.1.10/24', '192.168.1.1', '8.8.8.8'),
                         [NM, 'connection', 'modify', 'lan', 'ipv4.method', 'manual',
                          'ipv4.addresses', '192.168.1.10/24', 'ipv4.gateway', '192.168.1.1',
                          'ipv4.dns', '8.8.8.8'])
        self.assertEqual(self.commands.activate_connection('lan'), [NM, 'connection', 'up', 'lan'])
        self.assertEqual(self.commands.ethernet_lease('eth0'),
                         [NM, '-t', '-f', 'IP4.ADDRESS,IP4.GATEWAY,IP4.DNS', 'device', 'show', 'eth0'])


class EthernetServiceTest(unittest.TestCase):

    def test_disable_removes_orphan_vlans_only_on_physical_ethernet(self):
        links = [
            {'ifindex': 2, 'ifname': 'eth0'},
            {'ifindex': 3, 'ifname': 'eth1'},
            {'ifname': 'eth0.100', 'link_index': 2, 'linkinfo': {'info_kind': 'vlan'}},
            {'ifname': 'old-tag', 'link_index': 2, 'linkinfo': {'info_kind': 'vlan'}},
            {'ifname': 'eth1.100', 'link_index': 3, 'linkinfo': {'info_kind': 'vlan'}},
            {'ifname': 'macvlan0', 'link_index': 2, 'linkinfo': {'info_kind': 'macvlan'}}]
        script = Script([CommandResult(10), CommandResult(0, json.dumps(links)),
                         CommandResult(0), CommandResult(0),
                         CommandResult(0, 'Wired connection 1'), CommandResult(0), CommandResult(0)])
        service(script).apply_with_vlan('static', '10.0.0.2', '24', '', '', False, '')
        deletes = [run for run in script.runs if run[1:3] == ['link', 'delete']]
        self.assertEqual(deletes, [
            ['/usr/bin/ip', 'link', 'delete', 'dev', 'eth0.100'],
            ['/usr/bin/ip', 'link', 'delete', 'dev', 'old-tag']])
        self.assertEqual(script.runs[-1][-1], 'Wired connection 1')

    def test_disable_reports_interface_delete_failure(self):
        links = [{'ifname': 'eth0.100', 'link': 'eth0', 'linkinfo': {'info_kind': 'vlan'}}]
        script = Script([CommandResult(10), CommandResult(0, json.dumps(links)),
                         CommandResult(1, '', 'Operation not permitted')])
        with self.assertRaises(CommandFailedError):
            service(script).apply_with_vlan('dhcp', '', '', '', '', False, '')
        self.assertEqual(len(script.runs), 3)

    def test_disable_reports_invalid_interface_list(self):
        script = Script([CommandResult(10), CommandResult(0, 'invalid')])
        with self.assertRaises(CommandFailedError):
            service(script).apply_with_vlan('dhcp', '', '', '', '', False, '')
        self.assertEqual(len(script.runs), 2)

    def test_vlan_static_creates_tagged_interface_and_saves_ip(self):
        script = Script([CommandResult(10), CommandResult(0), CommandResult(0), CommandResult(0)])
        network = service(script)
        network.apply_with_vlan('static', '10.0.0.2', '24', '', '', True, '100')
        self.assertEqual(network.interface, 'eth0.100')
        self.assertEqual(script.runs[1], [NM, 'connection', 'add', 'type', 'vlan',
            'con-name', 'mulita-interna-vlan', 'ifname', 'eth0.100', 'dev', 'eth0', 'id', '100'])
        self.assertIn('10.0.0.2/24', script.runs[2])
        self.assertEqual(script.runs[3][-1], 'mulita-interna-vlan')

    def test_vlan_dhcp_reads_tagged_interface(self):
        script = Script([CommandResult(0, '100'), CommandResult(0), CommandResult(0),
                         CommandResult(0), *lease_results()])
        network = service(script)
        network.apply_with_vlan('dhcp', '', '', '', '', True, '200')
        self.assertEqual(network.interface, 'eth0.200')
        self.assertIn('eth0.200', script.runs[4])
        self.assertIn('eth0.200', script.runs[5])

    def test_vlan_disable_deletes_only_managed_profile_and_uses_base(self):
        script = Script([CommandResult(0, '100'), CommandResult(0),
                         CommandResult(0, '[]'),
                         CommandResult(0, 'Wired connection 1'), CommandResult(0), CommandResult(0)])
        network = service(script)
        network.apply_with_vlan('static', '10.0.0.2', '24', '', '', False, '')
        self.assertEqual(network.interface, 'eth0')
        self.assertEqual(script.runs[1], [NM, 'connection', 'delete', 'id', 'mulita-interna-vlan'])
        self.assertEqual(script.runs[-1][-1], 'Wired connection 1')

    def test_vlan_invalid_inputs_do_not_run_commands(self):
        for tag in ('0', '4095', '-1', 'bad', '1.5', ''):
            script = Script([])
            with self.assertRaises(ValidationError):
                service(script).apply_with_vlan('dhcp', '', '', '', '', True, tag)
            self.assertEqual(script.runs, [])

    def test_vlan_refresh_restores_saved_id_and_config(self):
        script = Script([CommandResult(0, '123'), CommandResult(0, 'manual\n10.0.0.2/24\n\n\n')])
        network = service(script)
        self.assertEqual(network.read_with_vlan().address, '10.0.0.2')
        self.assertEqual(network.vlan_id, 123)

    def test_vlan_create_failure_stops_before_ip_changes(self):
        script = Script([CommandResult(10), CommandResult(4, '', 'failed')])
        with self.assertRaises(CommandFailedError):
            service(script).apply_with_vlan('dhcp', '', '', '', '', True, '100')
        self.assertEqual(len(script.runs), 2)

    def test_read_uses_the_existing_connection(self):
        script = Script([
            CommandResult(0, 'Wired connection 1\n'),
            CommandResult(0, 'manual\n10.0.0.8/8\n10.0.0.1\n\n'),
        ])
        config = service(script).read()
        self.assertEqual(config.address, '10.0.0.8')
        self.assertEqual(config.prefix, 8)
        self.assertIn('Wired connection 1', script.runs[1])

    def test_read_without_connection_shows_the_lease(self):
        script = Script([CommandResult(0, '--\n'), *lease_results('IP4.DNS[1]:8.8.8.8\nIP4.DNS[2]:1.1.1.1\n')])
        config = service(script).read()
        self.assertEqual((config.address, config.prefix, config.gateway), ('192.168.0.45', 24, '192.168.0.1'))
        self.assertEqual(config.dns, '8.8.8.8, 1.1.1.1')
        self.assertEqual(script.runs[2][:4], ['/usr/bin/ip', '-j', 'addr', 'show'])
        self.assertEqual(script.runs[3][:4], ['/usr/bin/ip', '-j', 'route', 'show'])

    def test_read_dhcp_connection_uses_the_interface_lease(self):
        script = Script([
            CommandResult(0, 'Wired connection 1\n'),
            CommandResult(0, 'auto\n\n\n\n'),
            *lease_results(),
        ])
        config = service(script).read()
        self.assertEqual((config.mode, config.address, config.prefix, config.gateway),
                         (AddressMode.DHCP, '192.168.0.45', 24, '192.168.0.1'))

    def test_apply_dhcp_on_existing_connection(self):
        script = Script([
            CommandResult(0, 'Wired connection 1\n'),
            CommandResult(0),
            CommandResult(0),
            *lease_results(),
        ])
        config = service(script).apply_dhcp()
        self.assertEqual(config.address, '192.168.0.45')
        self.assertEqual(script.runs[1][4:6], ['ipv4.method', 'auto'])
        self.assertEqual(script.runs[2][1:3], ['connection', 'up'])

    def test_apply_static_creates_connection_when_missing(self):
        script = Script([CommandResult(0, '--\n'), CommandResult(0), CommandResult(0), CommandResult(0)])
        config = service(script).apply_static('192.168.0.20', '255.255.255.0', '192.168.0.1', '')
        self.assertEqual(config.prefix, 24)
        self.assertEqual(script.runs[1][1:3], ['connection', 'add'])
        self.assertIn('mulita-interna', script.runs[1])
        self.assertIn('192.168.0.20/24', script.runs[2])
        self.assertEqual(script.runs[3][-1], 'mulita-interna')

    def test_invalid_static_does_not_call_nmcli(self):
        script = Script([])
        with self.assertRaises(ValidationError):
            service(script).apply_static('300.1.1.1', '255.255.255.0')
        self.assertEqual(script.runs, [])

    def test_nmcli_failure_is_reported(self):
        script = Script([CommandResult(10, '', 'Device eth0 not found')])
        with self.assertRaises(CommandFailedError):
            service(script).read()
