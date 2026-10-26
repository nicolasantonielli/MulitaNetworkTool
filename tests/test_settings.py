from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mulita.adapters.backlight import SysfsBacklight
from mulita.adapters.settings_store import JsonSettingsStore, MemorySettingsStore
from mulita.core import settings as rules
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.settings import DisplaySettings, Language, Settings, Theme
from mulita.presentation.theme import Metrics
from mulita.services.settings import SettingsService


class DisplayRulesTest(unittest.TestCase):

    def test_pixel_density_from_resolution_and_diagonal(self):
        display = DisplaySettings(800, 480, 7)
        self.assertAlmostEqual(display.pixels_per_inch, 133.28, places=2)
        self.assertAlmostEqual(display.pixels_per_mm, 133.28 / 25.4, places=2)

    def test_ui_scale_multiplies_density(self):
        base = DisplaySettings(1024, 600, 7)
        scaled = DisplaySettings(1024, 600, 7, ui_scale=1.5)
        self.assertAlmostEqual(scaled.pixels_per_mm, base.pixels_per_mm * 1.5)

    def test_panel_is_five_inches(self):
        display = DisplaySettings()
        self.assertEqual((display.width, display.height, display.diagonal_inches), (800, 480, 5))

    def test_theme_validation(self):
        self.assertIs(rules.theme('light'), Theme.CLARO)
        with self.assertRaises(ValidationError):
            rules.theme('neon')

    def test_from_dict_falls_back_to_defaults(self):
        settings = rules.settings_from_dict({'display': {'width': 1280, 'diagonal_inches': 10.1}, 'theme': 'neon'})
        self.assertEqual(settings, Settings())

    def test_saved_display_is_ignored(self):
        settings = rules.settings_from_dict({'display': {'width': 1280, 'height': 800, 'diagonal_inches': 10.1},
                                             'theme': 'light', 'scale': 1.25})
        self.assertEqual((settings.display.width, settings.display.height, settings.display.diagonal_inches),
                         (800, 480, 5))
        self.assertEqual(settings.display.ui_scale, 1.25)
        self.assertIs(settings.theme, Theme.CLARO)

    def test_scale_outside_the_slider_is_clamped(self):
        self.assertEqual(rules.settings_from_dict({'scale': 4}).display.ui_scale, 1.25)
        self.assertEqual(rules.settings_from_dict({'scale': 0.1}).display.ui_scale, 0.5)

    def test_brightness_stays_between_one_and_one_hundred(self):
        self.assertEqual(rules.settings_from_dict({}).brightness, 100)
        self.assertEqual(rules.settings_from_dict({'brightness': 0}).brightness, 1)
        self.assertEqual(rules.settings_from_dict({'brightness': 40.4}).brightness, 40)
        self.assertEqual(rules.settings_from_dict({'brightness': 250}).brightness, 100)
        self.assertEqual(rules.settings_from_dict({'brightness': 'alto'}).brightness, 100)

    def test_scale_changes_every_metric(self):
        normal = Metrics.for_display(DisplaySettings())
        large = Metrics.for_display(DisplaySettings(ui_scale=1.5))
        self.assertAlmostEqual(large.mm, normal.mm * 1.5)
        self.assertGreater(large.font_body, normal.font_body)
        self.assertGreater(large.icon, normal.icon)


class MetricsTest(unittest.TestCase):

    def test_touch_target_keeps_physical_size(self):
        small = Metrics.for_display(DisplaySettings(800, 480, 7))
        dense = Metrics.for_display(DisplaySettings(1280, 800, 7))
        self.assertAlmostEqual(small.touch / small.mm, 9, delta=0.2)
        self.assertAlmostEqual(dense.touch / dense.mm, 9, delta=0.2)
        self.assertGreater(dense.touch, small.touch)


class JsonSettingsStoreTest(unittest.TestCase):

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name) / 'nested' / 'settings.json'
        self.store = JsonSettingsStore(self.path)

    def tearDown(self):
        self._dir.cleanup()

    def test_missing_file_gives_defaults(self):
        self.assertEqual(self.store.load(), Settings())

    def test_save_then_load(self):
        self.store.save(Settings(theme=Theme.CLARO))
        loaded = self.store.load()
        self.assertEqual(loaded.display, DisplaySettings())
        self.assertIs(loaded.theme, Theme.CLARO)
        self.assertFalse(self.path.with_suffix('.tmp').exists())
        saved = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(saved['theme'], 'light')
        self.assertEqual(saved['scale'], 1)

    def test_corrupt_file_gives_defaults(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{no es json', encoding='utf-8')
        self.assertEqual(self.store.load(), Settings())


class _MemoryBacklight:

    def __init__(self, ready: bool = True):
        self.ready = ready
        self.levels: list[int] = []

    def available(self) -> bool:
        return self.ready

    def apply(self, percent: int) -> None:
        self.levels.append(percent)


class SettingsServiceTest(unittest.TestCase):

    def setUp(self):
        self.store = MemorySettingsStore()
        self.light = _MemoryBacklight()
        self.service = SettingsService(self.store, self.light)
        self.notified: list[Settings] = []
        self.service.subscribe(self.notified.append)

    def test_set_theme(self):
        self.assertIs(self.service.set_theme('light').theme, Theme.CLARO)

    def test_language_switches_to_english(self):
        from mulita.presentation.i18n import tr
        updated = self.service.set_language('en')
        self.assertIs(updated.language, Language.EN)
        self.assertIs(self.store.load().language, Language.EN)
        self.assertEqual(tr('trace'), 'Trace')
        self.assertIs(rules.settings_from_dict({'language': 'en'}).language, Language.EN)
        self.assertIs(self.service.set_language('es').language, Language.ES)
        self.assertEqual(tr('trace'), 'Trazar')

    def test_set_scale_saves_and_notifies(self):
        updated = self.service.set_scale(1.25)
        self.assertEqual(updated.display.ui_scale, 1.25)
        self.assertEqual(self.notified, [updated])
        self.assertEqual(self.store.load().display.ui_scale, 1.25)

    def test_same_scale_does_not_notify(self):
        self.service.set_scale(1)
        self.assertEqual(self.notified, [])

    def test_brightness_is_saved_and_applied(self):
        self.assertEqual(self.light.levels, [100])
        updated = self.service.set_brightness(35)
        self.assertEqual(updated.brightness, 35)
        self.assertEqual(self.store.load().brightness, 35)
        self.assertEqual(self.light.levels, [100, 35])

    def test_missing_backlight_keeps_the_saved_level(self):
        self.light.ready = False
        updated = self.service.set_brightness(20)
        self.assertEqual(updated.brightness, 20)
        self.assertFalse(self.service.backlight_ready())


class SysfsBacklightTest(unittest.TestCase):

    def test_percent_maps_onto_the_panel_scale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            panel = root / 'panel'
            panel.mkdir()
            (panel / 'max_brightness').write_text('255\n', encoding='ascii')
            (panel / 'brightness').write_text('255\n', encoding='ascii')
            (root / 'kbd_backlight').mkdir()
            (root / 'kbd_backlight' / 'brightness').write_text('1\n', encoding='ascii')
            light = SysfsBacklight(root)
            self.assertTrue(light.available())
            light.apply(50)
            self.assertEqual((panel / 'brightness').read_text(encoding='ascii').strip(), '128')
            light.apply(1)
            self.assertEqual((panel / 'brightness').read_text(encoding='ascii').strip(), '3')

    def test_missing_device_does_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            light = SysfsBacklight(Path(directory))
            self.assertFalse(light.available())
            light.apply(40)

    def test_write_error_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            panel = root / 'panel'
            panel.mkdir()
            (panel / 'brightness').write_text('10\n', encoding='ascii')
            light = SysfsBacklight(root)
            (panel / 'brightness').chmod(0)
            try:
                with self.assertRaises(CommandFailedError):
                    light.apply(20)
            finally:
                (panel / 'brightness').chmod(0o644)


if __name__ == '__main__':
    unittest.main()
