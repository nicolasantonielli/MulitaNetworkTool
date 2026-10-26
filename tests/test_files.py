import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from mulita.config import Binaries
from mulita.core.commands import CommandFactory
from mulita.core.errors import ValidationError
from mulita.core.models import CommandResult
from mulita.services.files import CaptureFilesService, UsbDrive, list_usb_drives, parse_usb_drives
from tests.fakes import FakeRunner


class CaptureFilesTest(unittest.TestCase):

    def test_lists_pcap_files_from_both_folders(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'uno.pcap').write_bytes(b'abc')
            (root / 'nota.txt').write_text('no', encoding='utf-8')
            tap = root / 'tap'
            tap.mkdir()
            (tap / 'dos.pcap').write_bytes(b'12345')
            traces = root / 'trazas'
            traces.mkdir()
            (traces / 'ruta.csv').write_bytes(b'1,2')
            (traces / 'no.pcap').write_bytes(b'no')
            listed = CaptureFilesService(root).list_files()
            self.assertEqual(
                {(item.place, item.name, item.size) for item in listed},
                {('captura', 'uno.pcap', '3 B'), ('tap', 'dos.pcap', '5 B'), ('traza', 'ruta.csv', '3 B')})
            self.assertEqual({item.place_label for item in listed}, {'Captura', 'TAP', 'Traza'})

    def test_rename_copy_and_delete_stay_inside_the_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'uno.pcap').write_bytes(b'abc')
            service = CaptureFilesService(root)
            self.assertEqual(service.rename('captura', 'uno', 'tres'), 'tres.pcap')
            self.assertTrue((root / 'tres.pcap').is_file())
            self.assertEqual(service.copy('captura', 'tres.pcap', 'tres-copia'), 'tres-copia.pcap')
            self.assertEqual((root / 'tres-copia.pcap').read_bytes(), b'abc')
            service.delete('captura', 'tres.pcap')
            self.assertFalse((root / 'tres.pcap').exists())
            with self.assertRaises(ValidationError):
                service.rename('captura', '../fuera', 'x')
            with self.assertRaises(ValidationError):
                service.copy('captura', 'tres-copia', 'tres-copia')
            traces = root / 'trazas'
            traces.mkdir()
            (traces / 'ruta.csv').write_text('a,b\n', encoding='utf-8')
            self.assertEqual(service.rename('traza', 'ruta.csv', 'camino'), 'camino.csv')
            self.assertEqual((traces / 'camino.csv').read_text(encoding='utf-8'), 'a,b\n')
            pings = root / 'ping'
            pings.mkdir()
            (pings / 'prueba.txt').write_text('nota\n', encoding='utf-8')
            self.assertEqual(service.rename('ping', 'prueba.txt', 'final'), 'final.txt')
            self.assertTrue((pings / 'final.txt').is_file())

    def test_busy_capture_blocks_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'uno.pcap').write_bytes(b'abc')
            tap = root / 'tap'
            tap.mkdir()
            (tap / 'dos.pcap').write_bytes(b'zz')
            service = CaptureFilesService(root, capture_active=lambda: True)
            with self.assertRaises(ValidationError):
                service.delete('captura', 'uno.pcap')
            self.assertEqual(service.rename('tap', 'dos', 'dos2'), 'dos2.pcap')

    def test_export_copies_the_capture_onto_the_pendrive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'uno.pcap').write_bytes(b'abc')
            stick = root / 'stick'
            stick.mkdir()
            service = CaptureFilesService(
                root, drives=lambda: (UsbDrive('sda1', 'KINGSTON', str(stick)),))
            self.assertEqual(service.export('captura', 'uno.pcap', 'sda1'), 'uno.pcap')
            self.assertEqual((stick / 'uno.pcap').read_bytes(), b'abc')
            with self.assertRaises(ValidationError):
                service.export('captura', 'uno.pcap', 'sda1')
            with self.assertRaises(ValidationError):
                CaptureFilesService(root, drives=lambda: ()).export('captura', 'uno.pcap', 'sda1')

    def test_unmounted_usb_stick_is_listed_and_the_sd_card_is_not(self):
        listed = parse_usb_drives(json.dumps({'blockdevices': [
            {'name': 'mmcblk0', 'tran': 'mmc', 'type': 'disk', 'children': [
                {'name': 'mmcblk0p2', 'mountpoint': '/', 'type': 'part'},
            ]},
            {'name': 'sda', 'tran': 'usb', 'type': 'disk', 'children': [
                {'name': 'sda1', 'label': 'KINGSTON', 'mountpoint': None, 'type': 'part'},
            ]},
            {'name': 'sdb', 'tran': 'usb', 'type': 'disk', 'mountpoint': '/', 'label': 'root'},
        ]}))
        self.assertEqual([(item.device, item.label, item.mountpoint) for item in listed],
                         [('sda1', 'KINGSTON', '')])
        runner = FakeRunner({'/usr/bin/lsblk': CommandResult(0, json.dumps({'blockdevices': [
            {'name': 'sda', 'tran': 'usb', 'type': 'disk', 'children': [
                {'name': 'sda1', 'label': None, 'mountpoint': None, 'type': 'part'},
            ]},
        ]}))})
        service = CaptureFilesService(Path('.'), runner=runner, commands=CommandFactory(Binaries()))
        self.assertEqual(service.list_drives(), (UsbDrive('sda1', 'Pendrive', ''),))

    def test_sysfs_accepts_a_scsi_disk_hanging_off_usb(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            scsi = root / 'devices' / 'usb1' / '1-1' / '1-1.1.0' / 'host0' / 'target0.0.0' / '0.0.0.0'
            stick = scsi / 'block' / 'sda'
            (stick / 'sda1').mkdir(parents=True)
            (stick / 'removable').write_text('0', encoding='utf-8')
            card = root / 'devices' / 'mmc' / 'mmc0' / 'block' / 'mmcblk0'
            (card / 'mmcblk0p1').mkdir(parents=True)
            block = root / 'block'
            block.mkdir()
            _link_dir(stick / 'device', scsi)
            _link_dir(card / 'device', card.parent)
            _link_dir(block / 'sda', stick)
            _link_dir(block / 'mmcblk0', card)
            mounts = root / 'mounts'
            mounts.write_text('/dev/mmcblk0p1 / ext4 rw 0 0\n', encoding='utf-8')
            found = list_usb_drives(block, mounts)
            self.assertEqual([item.device for item in found], ['sda1'])


def _link_dir(link: Path, target: Path) -> None:
    subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)],
                   check=True, capture_output=True)
