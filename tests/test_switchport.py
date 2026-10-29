import json
import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from mulita.core.switchport import parse_frame
from mulita.services.switchport import SwitchPortService, read_link
from mulita.services.files import CaptureFilesService


SOURCE = bytes.fromhex('001122334455')


def tlv(kind, value):
    return struct.pack('!H', (kind << 9) | len(value)) + value


def lldp(ttl=120):
    payload = (tlv(1, b'\x04' + SOURCE) + tlv(2, b'\x05Gi1/0/24')
               + tlv(3, struct.pack('!H', ttl)) + tlv(5, b'SW-OFICINA')
               + tlv(4, b'Oficina') + tlv(6, b'Switch de prueba')
               + tlv(8, b'\x05\x01\xc0\xa8\x01\x02\x02\x00\x00\x00\x01\x00')
               + tlv(127, b'\x00\x80\xc2\x01\x00\x14')
               + tlv(127, b'\x00\x80\xc2\x03\x00\x14\x03LAN')
               + tlv(127, b'\x00\x12\xbb\x02\x01' + (0x400000 | (30 << 9)).to_bytes(3, 'big'))
               + tlv(0, b''))
    return bytes.fromhex('0180c200000e') + SOURCE + b'\x88\xcc' + payload


def cdp_tlv(kind, value):
    return struct.pack('!HH', kind, len(value) + 4) + value


class FrameTest(unittest.TestCase):
    def test_lldp_port_management_and_advertised_vlans(self):
        row, observed = parse_frame(lldp())
        self.assertEqual(row['name'], 'SW-OFICINA')
        self.assertEqual(row['port'], 'Gi1/0/24')
        self.assertEqual(row['addresses'], ['192.168.1.2'])
        self.assertEqual(row['pvid'], 20)
        self.assertEqual(row['vlans'], [{'id': 20, 'name': 'LAN'}])
        self.assertEqual(row['voice'], [{'id': 30, 'tagged': True}])
        self.assertEqual(observed, [])  # Anunciada no significa observada en tráfico.

    def test_cdp_port_model_and_native_vlan(self):
        addresses = struct.pack('!I', 1) + b'\x01\x01\xcc\x00\x04\x0a\x00\x00\x01'
        payload = (b'\x02\xb4\x00\x00' + cdp_tlv(1, b'Cisco-SW')
                   + cdp_tlv(3, b'GigabitEthernet1/0/8') + cdp_tlv(6, b'C9200')
                   + cdp_tlv(10, b'\x00\x64') + cdp_tlv(22, addresses))
        snap = b'\xaa\xaa\x03\x00\x00\x0c\x20\x00' + payload
        frame = bytes.fromhex('01000ccccccc') + SOURCE + struct.pack('!H', len(snap)) + snap
        row, _ = parse_frame(frame)
        self.assertEqual((row['protocol'], row['name'], row['port'], row['system'], row['pvid']),
                         ('CDP', 'Cisco-SW', 'GigabitEthernet1/0/8', 'C9200', 100))
        self.assertEqual(row['addresses'], ['10.0.0.1'])

    def test_tagged_and_double_tagged_traffic(self):
        frame = lldp()
        tagged = frame[:12] + b'\x88\xa8\x00\x64\x81\x00\x00\xc8' + frame[12:]
        row, tags = parse_frame(tagged)
        self.assertEqual(tags, [100, 200])
        self.assertEqual(row['pvid'], 20)

    def test_malformed_packets_and_missing_required_fields_are_ignored(self):
        for end in range(len(lldp()) - 1):
            row, _ = parse_frame(lldp()[:end])
            self.assertIsNone(row)
        self.assertIsNone(parse_frame(lldp()[:14] + tlv(5, b'fake') + tlv(0, b''))[0])


class ScanTest(unittest.TestCase):
    def test_receive_session_tracks_auxdata_vlan_and_withdrawal_and_closes_socket(self):
        for withdrawal in (False, True):
            with self.subTest(withdrawal=withdrawal), tempfile.TemporaryDirectory() as directory:
                cancel = threading.Event()
                class Receiver:
                    closed = False
                    frames = [lldp(), lldp(0)] if withdrawal else [lldp()]
                    def __enter__(self): return self
                    def __exit__(self, *args): self.closed = True
                    def bind(self, value): pass
                    def settimeout(self, value): pass
                    def setsockopt(self, *args): pass
                    def recvmsg(self, *args):
                        if not self.frames:
                            cancel.set()
                            raise socket.timeout()
                        aux = struct.pack('IIIHHHH', 1 << 4, 0, 0, 0, 0, 55, 0x8100)
                        return self.frames.pop(0), [(263, 8, aux)], 0, ('eth0', 0, 0)
                receiver = Receiver()
                with patch.object(socket, 'AF_PACKET', 17, create=True), \
                     patch.object(socket, 'socket', return_value=receiver), \
                     patch.object(socket, 'if_nametoindex', return_value=1, create=True), \
                     patch('mulita.services.switchport.read_link', return_value={'carrier': '1'}):
                    report = SwitchPortService(Path(directory)).scan('eth0', 5, cancel, lambda _: None)
                self.assertTrue(receiver.closed)
                self.assertEqual(report['vlans'], [55])
                self.assertEqual(len(report['neighbors']), 0 if withdrawal else 1)
                self.assertTrue(report['cancelled'])

    def test_link_reading_and_report_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'eth0').mkdir()
            (root / 'eth0' / 'speed').write_text('1000')
            (root / 'eth0' / 'carrier').write_text('1')
            self.assertEqual(read_link('eth0', root)['speed'], '1000')
            (root / 'eth0' / 'speed').write_text('-1')
            self.assertEqual(read_link('eth0', root)['speed'], '')
            service = SwitchPortService(root / 'reports')
            report = service.scan('eth0', 5, threading.Event(), lambda _: None, simulated=True)
            self.assertTrue(report['simulated'])
            self.assertEqual(json.loads(service.save(report).read_text(encoding='utf-8')), report)
            self.assertNotEqual(service.save(report), service.save(report))

    def test_saved_report_is_available_in_the_file_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = SwitchPortService(root / 'puerto-switch')
            path = service.save({'simulated': True})
            files = CaptureFilesService(root)
            self.assertEqual(files.list_files()[0].name, path.name)
            self.assertEqual(files.copy('puerto-switch', path.name, 'copia'), 'copia.json')


if __name__ == '__main__':
    unittest.main()
