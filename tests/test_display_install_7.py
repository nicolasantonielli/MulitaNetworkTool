from pathlib import Path
import tempfile
import unittest

from scripts.configure_display import configure_file, configure_text as configure_five
from scripts.configure_display_7 import configure_text
from tests.test_display_install import ORIGINAL


class SevenInchInstallTest(unittest.TestCase):
    def test_switching_back_to_five_replaces_waveshare_and_is_repeatable(self):
        seven = configure_text(ORIGINAL)
        five = configure_five(seven)
        active = [line for line in five.splitlines() if not line.startswith('#')]
        self.assertIn('dtoverlay=vc4-kms-v3d', active)
        self.assertIn('dtoverlay=vc4-kms-dsi-7inch,disable_touch', active)
        self.assertIn('dtoverlay=rpi-ft5406', active)
        self.assertNotIn('dtoverlay=vc4-kms-dsi-waveshare-panel,7_0_inchH', active)
        self.assertEqual(configure_five(five), five)
        self.assertEqual(configure_text(configure_text(five)), configure_text(five))

    def test_applies_dsi1_and_preserves_other_hardware(self):
        updated = configure_text(ORIGINAL)
        self.assertIn('dtoverlay=vc4-kms-dsi-waveshare-panel,7_0_inchH\n', updated)
        self.assertIn('#dtoverlay=vc4-kms-dsi-waveshare-panel,7_0_inchH,dsi0', updated)
        self.assertIn('[cm4]\notg_mode=1', updated)
        self.assertIn('dtoverlay=dwc2,dr_mode=host', updated)
        self.assertEqual(updated.splitlines().count('dtoverlay=vc4-kms-v3d'), 1)
        self.assertEqual(configure_text(updated), updated)

    def test_replaces_old_panel_and_manual_dsi0_configuration(self):
        original = configure_five(ORIGINAL) + (
            '[pi4]\ndtoverlay=vc4-kms-dsi-waveshare-panel,7_0_inchH,dsi0\n'
            'dtoverlay=vc4-fkms-v3d\n')
        updated = configure_text(original)
        active = [line for line in updated.splitlines() if not line.startswith('#')]
        self.assertNotIn('dtoverlay=rpi-ft5406', active)
        self.assertNotIn('dtoverlay=vc4-kms-dsi-7inch,disable_touch', active)
        self.assertNotIn('dtoverlay=vc4-fkms-v3d', active)
        self.assertNotIn('dtoverlay=vc4-kms-dsi-waveshare-panel,7_0_inchH,dsi0', active)
        self.assertEqual(configure_text(updated), updated)

    def test_preserves_backup_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.txt'
            path.write_text(ORIGINAL, encoding='utf-8')
            self.assertTrue(configure_file(path, configure_text))
            self.assertFalse(configure_file(path, configure_text))
            self.assertEqual(path.with_name('config.txt.mulita-bak').read_text(encoding='utf-8'), ORIGINAL)

    def test_incomplete_old_or_new_block_fails_without_writing(self):
        for marker in ('# mulita-waveshare-7 begin', '# mulita-btt-pitft50-v1 begin'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'config.txt'
                original = ORIGINAL + marker + '\nimportant=true\n'
                path.write_text(original, encoding='utf-8')
                with self.assertRaises(ValueError):
                    configure_file(path, configure_text)
                self.assertEqual(path.read_text(encoding='utf-8'), original)

    def test_installer_uses_seven_inch_helper_and_lf(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / 'install-lite.sh').read_bytes()
        self.assertNotIn(b'\r', script)
        self.assertIn(b'scripts/configure_display_7.py', script)
        self.assertIn(b'DISPLAY_OVERLAYS=(vc4-kms-v3d vc4-kms-dsi-waveshare-panel)', script)
