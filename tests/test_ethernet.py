import unittest

from mulita.config import Binaries
from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.models import AddressMode, CommandResult, EthernetConfig
from mulita.core.parsers import parse_connection_name, parse_nmcli_device_ipv4, parse_nmcli_ipv4
from mulita.services.ethernet import EthernetService

NM = '/usr/bin/nmcli'
LEASE = '''IP4.ADDRESS[1]:192.168.0.45/24
IP4.GATEWAY:192.168.0.1
IP4.DNS[1]:192.168.0.1
IP4.DNS[2]:8.8.8.8
'''


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
        script = Script([CommandResult(0, '--\n'), CommandResult(0, LEASE)])
        config = service(script).read()
        self.assertEqual(config.address, '192.168.0.45')
        self.assertEqual(config.dns, '192.168.0.1, 8.8.8.8')
        self.assertEqual(script.runs[1][1:4], ['-t', '-f', 'IP4.ADDRESS,IP4.GATEWAY,IP4.DNS'])

    def test_read_dhcp_connection_uses_the_interface_lease(self):
        script = Script([
            CommandResult(0, 'Wired connection 1\n'),
            CommandResult(0, 'auto\n\n\n\n'),
            CommandResult(0, LEASE),
        ])
        config = service(script).read()
        self.assertEqual((config.mode, config.address, config.prefix, config.gateway),
                         (AddressMode.DHCP, '192.168.0.45', 24, '192.168.0.1'))

    def test_apply_dhcp_on_existing_connection(self):
        script = Script([
            CommandResult(0, 'Wired connection 1\n'),
            CommandResult(0),
            CommandResult(0),
            CommandResult(0, LEASE),
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
