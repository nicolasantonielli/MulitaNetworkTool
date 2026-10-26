from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.configure_display import configure_file, configure_text


ORIGINAL = '''# Raspberry Pi OS Lite
camera_auto_detect=1
display_auto_detect=1
dtoverlay=vc4-kms-v3d
disable_fw_kms_setup=1
arm_64bit=1
[cm4]
otg_mode=1
[cm5]
dtoverlay=dwc2,dr_mode=host
[pi5]
dtoverlay=nospi10
[all]
# mulita-kiosk
disable_splash=1
'''


class DisplayInstallTest(unittest.TestCase):
    def test_configures_firmware_touch_in_all_section_and_keeps_other_devices(self):
        updated = configure_text(ORIGINAL)
        for line in ('camera_auto_detect=1', 'dtoverlay=vc4-kms-v3d',
                     'disable_fw_kms_setup=1', '[cm4]\notg_mode=1',
                     '[cm5]\ndtoverlay=dwc2,dr_mode=host', '[pi5]\ndtoverlay=nospi10'):
            self.assertIn(line, updated)
        self.assertIn('[all]\ndisplay_auto_detect=0\n'
                      'dtoverlay=vc4-kms-dsi-7inch,disable_touch\n'
                      'dtoverlay=rpi-ft5406\ndisable_touchscreen=0\ndisable_splash=1', updated)
        self.assertNotIn('\ndisplay_auto_detect=1\n', updated)

    def test_repeated_installation_does_not_duplicate_settings(self):
        once = configure_text(ORIGINAL)
        self.assertEqual(configure_text(once), once)
        self.assertEqual(once.count('\ndtoverlay=rpi-ft5406\n'), 1)

    def test_adopts_the_manual_fix_without_duplicating_active_overlays(self):
        manual = ORIGINAL.replace('display_auto_detect=1', 'display_auto_detect=0')
        manual += ('dtoverlay=vc4-kms-dsi-7inch,disable_touch\n'
                   'dtoverlay=rpi-ft5406\ndisable_touchscreen=0\n')
        updated = configure_text(manual)
        self.assertEqual(updated.count('\ndtoverlay=rpi-ft5406\n'), 1)
        self.assertEqual(updated.count('\ndtoverlay=vc4-kms-dsi-7inch,disable_touch\n'), 1)
        self.assertEqual(configure_text(updated), updated)

    def test_replaces_conflicting_settings_in_conditional_sections(self):
        text = ORIGINAL + ('[pi4]\n display_auto_detect = 1 # old value\n'
                           'dtoverlay = rpi-ft5406,touchscreen-inverted-x\n'
                           'dtoverlay=vc4-kms-dsi-7inch,invx,invy\n'
                           'disable_touchscreen=1\n')
        updated = configure_text(text)
        active = [line.strip() for line in updated.splitlines() if not line.lstrip().startswith('#')]
        self.assertEqual([line for line in active if line.startswith('display_auto_detect')],
                         ['display_auto_detect=0'])
        self.assertNotIn('disable_touchscreen=1', active)
        self.assertEqual(active.count('dtoverlay=rpi-ft5406'), 1)

    def test_backup_keeps_original_even_after_another_install(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.txt'
            path.write_text(ORIGINAL, encoding='utf-8')
            self.assertTrue(configure_file(path))
            self.assertFalse(configure_file(path))
            path.write_text(path.read_text(encoding='utf-8') + '# user note\n', encoding='utf-8')
            self.assertTrue(configure_file(path))
            self.assertEqual(path.with_name('config.txt.mulita-bak').read_text(encoding='utf-8'), ORIGINAL)
            self.assertIn('# user note', path.read_text(encoding='utf-8'))

    def test_incomplete_managed_block_does_not_modify_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.txt'
            original = ORIGINAL + '# mulita-btt-pitft50-v1 begin\nimportant=true\n'
            path.write_text(original, encoding='utf-8')
            with self.assertRaises(ValueError):
                configure_file(path)
            self.assertEqual(path.read_text(encoding='utf-8'), original)

    def test_failed_replacement_preserves_config_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.txt'
            path.write_text(ORIGINAL, encoding='utf-8')
            with patch('scripts.configure_display.os.replace', side_effect=OSError('write failed')):
                with self.assertRaises(OSError):
                    configure_file(path)
            self.assertEqual(path.read_text(encoding='utf-8'), ORIGINAL)
            self.assertEqual(list(path.parent.glob('.mulita-config-*')), [])


if __name__ == '__main__':
    unittest.main()
