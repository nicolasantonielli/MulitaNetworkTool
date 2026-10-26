import tempfile
import unittest
from pathlib import Path

from mulita.core.errors import ValidationError
from mulita.services.files import CaptureFilesService


class CaptureFilesTest(unittest.TestCase):

    def test_lists_pcap_files_from_both_folders(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'uno.pcap').write_bytes(b'abc')
            (root / 'nota.txt').write_text('no', encoding='utf-8')
            tap = root / 'tap'
            tap.mkdir()
            (tap / 'dos.pcap').write_bytes(b'12345')
            listed = CaptureFilesService(root).list_files()
            self.assertEqual(
                {(item.place, item.name, item.size) for item in listed},
                {('captura', 'uno.pcap', '3 B'), ('tap', 'dos.pcap', '5 B')})
            self.assertEqual({item.place_label for item in listed}, {'Captura', 'TAP'})

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
