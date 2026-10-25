from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mulita.adapters.settings_store import JsonSettingsStore, MemorySettingsStore
from mulita.core import settings as rules
from mulita.core.errors import ValidationError
from mulita.core.settings import DisplaySettings, Settings, Theme
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

    def test_scale_out_of_range_falls_back(self):
        settings = rules.settings_from_dict({'scale': 4, 'theme': 'dark'})
        self.assertEqual(settings.display.ui_scale, 1)

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


class SettingsServiceTest(unittest.TestCase):

    def setUp(self):
        self.store = MemorySettingsStore()
        self.service = SettingsService(self.store)
        self.notified: list[Settings] = []
        self.service.subscribe(self.notified.append)

    def test_set_theme(self):
        self.assertIs(self.service.set_theme('light').theme, Theme.CLARO)

    def test_set_scale_saves_and_notifies(self):
        updated = self.service.set_scale(1.25)
        self.assertEqual(updated.display.ui_scale, 1.25)
        self.assertEqual(self.notified, [updated])
        self.assertEqual(self.store.load().display.ui_scale, 1.25)

    def test_same_scale_does_not_notify(self):
        self.service.set_scale(1)
        self.assertEqual(self.notified, [])


if __name__ == '__main__':
    unittest.main()
