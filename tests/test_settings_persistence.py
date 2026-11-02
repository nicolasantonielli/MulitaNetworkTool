"""Los errores de persistencia se presentan sin publicar preferencias fallidas."""
import unittest
from types import SimpleNamespace

from tests.qt_support import qt_app
from mulita.adapters.settings_store import MemorySettingsStore
from mulita.config import AppConfig
from mulita.core.errors import PersistenceError
from mulita.core.messages import message
from mulita.core.settings import HomeOrder, Settings
from mulita.presentation.i18n import Translator
from mulita.services.settings import SettingsService
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.system import I18nController, SettingsController


class FailingStore(MemorySettingsStore):
    def save(self, settings):
        raise PersistenceError(message('settingsSaveFailed'))


class SettingsPersistenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def test_all_preference_actions_report_failed_save_without_changing_state(self):
        actions = (
            ('setLanguage', ('en',)),
            ('setTheme', ('light',)),
            ('setScale', (1.25,)),
            ('setRotation', (90,)),
            ('setResizeTiles', (False,)),
            ('setBrightness', (50.0,)),
            ('setHomeScreens', ('[]',)),
            ('resetTileOrder', ()),
        )
        for method, arguments in actions:
            with self.subTest(method=method):
                original = Settings(home=HomeOrder(screens=(('wifi',),)))
                store = FailingStore(original)
                levels = []
                backlight = SimpleNamespace(apply=levels.append, available=lambda: True)
                service = SettingsService(store, backlight)
                ctx = BridgeContext(AppConfig(test_mode=True), getattr(SimpleNamespace(settings=service), 'settings', None), None, Notifier())
                controller = SettingsController(ctx)
                catalog = I18nController(ctx)
                notifications, changes, catalog_changes = [], [], []
                ctx.notifier.notified.connect(lambda *args: notifications.append(args))
                controller.changed.connect(lambda: changes.append(True))
                catalog.changed.connect(lambda: catalog_changes.append(True))
                getattr(controller, method)(*arguments)
                self.assertEqual(service.current, original)
                self.assertEqual(store.load(), original)
                self.assertEqual(changes, [])
                self.assertEqual(catalog_changes, [])
                self.assertEqual(catalog.language, 'es')
                self.assertEqual(levels, [original.brightness])
                self.assertEqual(len(notifications), 1)
                self.assertEqual(notifications[0][0], 'error')
                self.assertEqual(notifications[0][2], Translator('es').tr('settingsSaveFailed'))

    def test_successful_reset_notifies_after_preferences_are_saved(self):
        store = MemorySettingsStore(Settings(home=HomeOrder(screens=(('wifi',),))))
        service = SettingsService(store, SimpleNamespace(apply=lambda _: None))
        ctx = BridgeContext(AppConfig(test_mode=True), getattr(SimpleNamespace(settings=service), 'settings', None), None, Notifier())
        controller = SettingsController(ctx)
        notifications = []
        ctx.notifier.notified.connect(lambda *args: notifications.append((args[0], store.load())))
        controller.resetTileOrder()
        self.assertEqual(notifications, [('success', Settings())])
