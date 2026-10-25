from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mulita.adapters.settings_store import JsonSettingsStore, MemorySettingsStore
from mulita.core import settings as rules
from mulita.core.errors import ValidationError
from mulita.core.settings import DISPLAY_PRESETS, DisplaySettings, Settings, Theme
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

    def test_validation_normalizes_values(self):
        display = rules.display_settings('1024', 600.4, '10.123', 0, 1)
        self.assertEqual((display.width, display.height), (1024, 600))
        self.assertEqual(display.diagonal_inches, 10.12)
        self.assertFalse(display.fullscreen)

    def test_validation_rejects_out_of_range(self):
        for args in ((100, 480, 7), (800, 9999, 7), (800, 480, 1), (800, 480, 'x')):
            with self.assertRaises(ValidationError):
                rules.display_settings(*args)
        with self.assertRaises(ValidationError):
            rules.display_settings(800, 480, 7, True, 3)

    def test_theme_validation(self):
        self.assertIs(rules.theme('light'), Theme.CLARO)
        with self.assertRaises(ValidationError):
            rules.theme('neon')

    def test_from_dict_falls_back_to_defaults(self):
        settings = rules.settings_from_dict({'display': {'width': -1}, 'theme': 'neon'})
        self.assertEqual(settings, Settings())

    def test_round_trip_through_dict(self):
        original = Settings(DisplaySettings(1280, 800, 10.1, False, 1.25), Theme.CLARO)
        self.assertEqual(rules.settings_from_dict(original.to_dict()), original)


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
        settings = Settings(DisplaySettings(1024, 600, 7), Theme.CLARO)
        self.store.save(settings)
        self.assertEqual(self.store.load(), settings)
        self.assertFalse(self.path.with_suffix('.tmp').exists())
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['theme'], 'light')

    def test_corrupt_file_gives_defaults(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{no es json', encoding='utf-8')
        self.assertEqual(self.store.load(), Settings())


class SettingsServiceTest(unittest.TestCase):

    def setUp(self):
        self.store = MemorySettingsStore()
        self.service = SettingsService(self.store)
        self.notified: list[Settings] = []
        self.service.subscribe(self.notified.append)

    def test_update_display_saves_and_notifies(self):
        result = self.service.update_display(1024, 600, 7, True, 1)
        self.assertEqual(self.store.settings, result)
        self.assertEqual(self.notified, [result])

    def test_unchanged_value_does_not_notify(self):
        self.service.update_display(800, 480, 5, True, 1)
        self.assertEqual(self.notified, [])

    def test_invalid_display_keeps_previous(self):
        with self.assertRaises(ValidationError):
            self.service.update_display(10, 10, 7, True, 1)
        self.assertEqual(self.service.current, Settings())

    def test_preset_keeps_fullscreen_and_scale(self):
        self.service.update_display(800, 480, 7, False, 1.25)
        index = next(i for i, p in enumerate(DISPLAY_PRESETS) if p.diagonal_inches == 10.1)
        display = self.service.apply_preset(index).display
        self.assertEqual((display.width, display.diagonal_inches), (1024, 10.1))
        self.assertFalse(display.fullscreen)
        self.assertEqual(display.ui_scale, 1.25)

    def test_set_theme(self):
        self.assertIs(self.service.set_theme('light').theme, Theme.CLARO)


if __name__ == '__main__':
    unittest.main()
