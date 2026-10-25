import unittest

from mulita.config import Binaries
from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.models import CommandResult, WifiNetwork
from mulita.core.parsers import parse_wifi_device, parse_wifi_list
from mulita.services.wifi import WifiService

NM = '/usr/bin/nmcli'
DEVICES = 'wlan0:wifi\neth0:ethernet\np2p-dev-wlan0:wifi-p2p\n'
LIST = ''':Casa\\:Norte:80:WPA2
*:Oficina:55:WPA1 WPA2
 :Invitados:40:
 :Casa\\:Norte:20:WPA2
'''


class Script:
    def __init__(self, replies):
        self.replies = list(replies)
        self.runs = []

    def run(self, argv, timeout=None):
        self.runs.append(list(argv))
        return self.replies.pop(0)


def service(script: Script) -> WifiService:
    return WifiService(script, CommandFactory(Binaries()))


class WifiRulesTest(unittest.TestCase):

    def test_parse_list_keeps_the_strongest_and_marks_the_active_one(self):
        networks = parse_wifi_list(LIST)
        self.assertEqual([item.ssid for item in networks], ['Oficina', 'Casa:Norte', 'Invitados'])
        self.assertTrue(networks[0].active)
        self.assertEqual(networks[1], WifiNetwork('Casa:Norte', 80, 'WPA2', False))
        self.assertFalse(networks[2].secure)

    def test_parse_device_skips_ethernet_and_p2p(self):
        self.assertEqual(parse_wifi_device(DEVICES), 'wlan0')
        self.assertIsNone(parse_wifi_device('eth0:ethernet\n'))

    def test_ssid_and_password_validation(self):
        self.assertEqual(validation.wifi_ssid(' Casa '), 'Casa')
        with self.assertRaises(ValidationError):
            validation.wifi_ssid('-oculta')
        self.assertEqual(validation.wifi_password('', required=False), '')
        with self.assertRaises(ValidationError):
            validation.wifi_password('   ', required=True)


class WifiServiceTest(unittest.TestCase):

    def test_scan_lists_networks_on_wlan0(self):
        script = Script([CommandResult(0, DEVICES), CommandResult(0), CommandResult(0, LIST)])
        device, networks = service(script).scan()
        self.assertEqual(device, 'wlan0')
        self.assertEqual(networks[0].ssid, 'Oficina')
        self.assertEqual(script.runs[1][1:4], ['device', 'wifi', 'rescan'])
        self.assertEqual(script.runs[2][4:7], ['device', 'wifi', 'list'])

    def test_scan_without_wifi_is_empty(self):
        script = Script([CommandResult(0, 'eth0:ethernet\n')])
        self.assertEqual(service(script).scan(), (None, ()))

    def test_connect_saves_key_management_and_password(self):
        script = Script([
            CommandResult(0, DEVICES),
            CommandResult(10, '', 'unknown'),
            CommandResult(0),
            CommandResult(0),
        ])
        self.assertEqual(service(script).connect('Oficina', 'secreto', True), 'Oficina')
        self.assertEqual(script.runs[1][:4], [NM, 'connection', 'delete', 'id'])
        self.assertEqual(script.runs[2], [
            NM, 'connection', 'add', 'type', 'wifi', 'ifname', 'wlan0',
            'con-name', 'Oficina', 'ssid', 'Oficina',
            '802-11-wireless-security.key-mgmt', 'wpa-psk',
            '802-11-wireless-security.psk', 'secreto'])
        self.assertEqual(script.runs[3], [NM, 'connection', 'up', 'Oficina', 'ifname', 'wlan0'])

    def test_existing_profile_gets_key_management_before_activation(self):
        script = Script([
            CommandResult(0, DEVICES),
            CommandResult(0),
            CommandResult(4, '', 'already exists'),
            CommandResult(0),
            CommandResult(0),
        ])
        self.assertEqual(service(script).connect('Oficina', 'secreto', True), 'Oficina')
        self.assertEqual(script.runs[3], [
            NM, 'connection', 'modify', 'Oficina',
            '802-11-wireless-security.key-mgmt', 'wpa-psk',
            '802-11-wireless-security.psk', 'secreto'])

    def test_open_network_does_not_send_a_password(self):
        script = Script([CommandResult(0, DEVICES), CommandResult(0)])
        service(script).connect('Invitados', '', False)
        self.assertNotIn('password', script.runs[1])

    def test_secure_network_requires_a_password_before_nmcli(self):
        script = Script([])
        with self.assertRaises(ValidationError):
            service(script).connect('Oficina', '', True)
        self.assertEqual(script.runs, [])

    def test_connect_failure_is_reported(self):
        script = Script([
            CommandResult(0, DEVICES),
            CommandResult(10, '', 'not found'),
            CommandResult(4, '', 'Secrets were required'),
            CommandResult(10, '', 'no connection'),
        ])
        with self.assertRaises(CommandFailedError):
            service(script).connect('Oficina', 'mala', True)
