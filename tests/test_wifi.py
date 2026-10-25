import unittest

from mulita.config import Binaries
from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.models import CommandResult, WifiLink, WifiNetwork
from mulita.core.parsers import build_wifi_link, parse_wifi_device, parse_wifi_list
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

    def test_status_reads_the_link_without_rescanning(self):
        script = Script([CommandResult(0, DEVICES), *([CommandResult(0, '')] * 8)])
        link = service(script).status()
        self.assertEqual(link.interface, 'wlan0')
        self.assertFalse(any('rescan' in run for run in script.runs))
        self.assertEqual(script.runs[5][1:], ['dev', 'wlan0', 'link'])

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

    def test_link_keeps_address_and_radio(self):
        link = build_wifi_link(
            'wlan0',
            '[{"address":"b8:27:eb:11:22:33","addr_info":['
            '{"family":"inet","local":"192.168.1.50","prefixlen":24},'
            '{"family":"inet6","local":"fe80::1"}]}]',
            '[{"dst":"default","gateway":"192.168.1.1","dev":"wlan0"}]',
            'IP4.DNS[1]:8.8.8.8\nIP4.DNS[2]:1.1.1.1\n',
            '*:aa\\:bb\\:cc\\:dd\\:ee\\:ff:36:5180 MHz:270 Mbit/s:55:WPA2\n',
            'Connected to aa:bb:cc:dd:ee:ff (on wlan0)\n'
            '\tSSID: Oficina\n\tfreq: 5180\n'
            '\tRX: 1048576 bytes (800 packets)\n\tTX: 2097152 bytes (900 packets)\n'
            '\tsignal: -48 dBm\n'
            '\trx bitrate: 390.0 MBit/s VHT-MCS 9 80MHz short GI VHT-NSS 1\n'
            '\ttx bitrate: 433.3 MBit/s VHT-MCS 9 80MHz short GI VHT-NSS 2\n'
            '\tdtim period: 2\n\tbeacon int: 100\n',
            'Interface wlan0\n\taddr b8:27:eb:11:22:33\n\ttype managed\n'
            '\tchannel 36 (5180 MHz), width: 80 MHz, center1: 5210 MHz\n'
            '\ttxpower 20.00 dBm\n',
            'Station aa:bb:cc:dd:ee:ff (on wlan0)\n'
            '\ttx retries:\t3\n\ttx failed:\t1\n\tbeacon loss:\t0\n'
            '\tsignal:\t-47 [-50, -48] dBm\n\tsignal avg:\t-49 dBm\n'
            '\tconnected time:\t3661 seconds\n',
            'frequency:\t\t5180 MHz [in use]\n\tnoise:\t\t-95 dBm\n',
            (WifiNetwork('Oficina', 55, 'WPA2', True),))
        facts = dict(link.facts())
        self.assertEqual(facts['Red'], 'Oficina')
        self.assertEqual(facts['BSSID'], 'aa:bb:cc:dd:ee:ff')
        self.assertEqual(facts['Seguridad'], 'WPA2')
        self.assertEqual(facts['Modo'], 'Infraestructura')
        self.assertEqual(facts['MAC'], 'b8:27:eb:11:22:33')
        self.assertEqual(facts['Dirección IP'], '192.168.1.50')
        self.assertEqual(facts['Máscara'], '255.255.255.0 (/24)')
        self.assertEqual(facts['Puerta de enlace'], '192.168.1.1')
        self.assertEqual(facts['DNS'], '8.8.8.8, 1.1.1.1')
        self.assertEqual(facts['IPv6'], 'fe80::1')
        self.assertEqual(facts['Banda'], '5 GHz')
        self.assertEqual(facts['Canal'], '36')
        self.assertEqual(facts['Frecuencia'], '5180 MHz')
        self.assertEqual(facts['Ancho de canal'], '80 MHz')
        self.assertEqual(facts['Frecuencia central'], '5210 MHz')
        self.assertEqual(facts['Señal'], '-47 dBm · media -49 dBm · 55 %')
        self.assertEqual(facts['Ruido'], '-95 dBm')
        self.assertEqual(facts['SNR'], '48 dB')
        self.assertEqual(facts['Velocidad de bajada'], '390.0 Mbit/s')
        self.assertEqual(facts['Velocidad de subida'], '433.3 Mbit/s')
        self.assertEqual(facts['MCS de bajada'], 'VHT-MCS 9 · NSS 1 · 80 MHz · GI corto')
        self.assertEqual(facts['MCS de subida'], 'VHT-MCS 9 · NSS 2 · 80 MHz · GI corto')
        self.assertEqual(facts['Potencia de transmisión'], '20 dBm')
        self.assertEqual(facts['Tiempo en línea'], '1 h 1 min')
        self.assertEqual(facts['Beacon'], '100 TU')
        self.assertEqual(facts['DTIM'], '2')
        self.assertEqual(facts['Reintentos de envío'], '3')
        self.assertEqual(facts['Envíos fallidos'], '1')
        self.assertEqual(facts['Beacons perdidos'], '0')
        self.assertEqual(facts['Recibido'], '1 MiB')
        self.assertEqual(facts['Enviado'], '2 MiB')

    def test_link_without_iw_keeps_the_address(self):
        link = build_wifi_link(
            'wlan0',
            '[{"address":"b8:27:eb:11:22:33","addr_info":['
            '{"family":"inet","local":"10.0.0.8","prefixlen":8}]}]',
            '[]',
            'IP4.GATEWAY:10.0.0.1\nIP4.DNS[1]:10.0.0.1\n',
            '*:aa\\:bb\\:cc\\:dd\\:ee\\:01:6:2437 MHz:54 Mbit/s:40:WPA2\n',
            'Not connected.\n', '', '', '', ())
        facts = dict(link.facts())
        self.assertEqual(facts['Dirección IP'], '10.0.0.8')
        self.assertEqual(facts['Máscara'], '255.0.0.0 (/8)')
        self.assertEqual(facts['Puerta de enlace'], '10.0.0.1')
        self.assertEqual(facts['Banda'], '2.4 GHz')
        self.assertEqual(facts['Canal'], '6')
        self.assertEqual(facts['Velocidad de bajada'], '54 Mbit/s')
        self.assertNotIn('MCS de bajada', facts)

    def test_connect_failure_is_reported(self):
        script = Script([
            CommandResult(0, DEVICES),
            CommandResult(10, '', 'not found'),
            CommandResult(4, '', 'Secrets were required'),
            CommandResult(10, '', 'no connection'),
        ])
        with self.assertRaises(CommandFailedError):
            service(script).connect('Oficina', 'mala', True)
