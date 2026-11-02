from pathlib import Path
from types import SimpleNamespace
import unittest
from PyQt5 import sip
from PyQt5.QtCore import QUrl
from PyQt5.QtQml import QQmlComponent, QQmlEngine
from tests.qt_support import qt_app
from tests.fakes import FakeBacklight
from mulita.adapters.settings_store import MemorySettingsStore
from mulita.config import AppConfig
from mulita.core.models import AddressMode, EthernetConfig
from mulita.services.settings import SettingsService
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.ipv4 import IPv4Controller
from mulita.ui.qt.bridge.system import Appearance, I18nController


class IPv4FormTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def test_loaded_profiles_clear_optional_fields_and_apply_current_values(self):
        service = SettingsService(MemorySettingsStore(), FakeBacklight())
        ctx = BridgeContext(AppConfig(test_mode=True), SimpleNamespace(settings=service), None, Notifier())
        controller = IPv4Controller(ctx, None, lambda: 'test0', 'wifiIp')
        appearance, catalog = Appearance(ctx), I18nController(ctx)
        engine = QQmlEngine()
        context = engine.rootContext()
        for name, value in [('ui', appearance), ('i18n', catalog), ('testController', controller)]:
            context.setContextProperty(name, value)
        component = QQmlComponent(engine)
        path = Path(__file__).resolve().parents[1] / 'mulita/ui/qt/qml/components/test.qml'
        component.setData(b'import QtQuick 2.15\nIPv4Form { controller: testController }',
                          QUrl.fromLocalFile(str(path)))
        self.assertEqual(component.errors(), [])
        form = component.create()
        self.assertIsNotNone(form)
        try:
            controller._show(EthernetConfig(AddressMode.ESTATICA, '192.0.2.5', 24, '192.0.2.1', '1.1.1.1'))
            self.assertEqual(form.property('gateway'), '192.0.2.1')
            controller._show(EthernetConfig(AddressMode.ESTATICA, '192.0.2.6', 24, '', ''))
            self.assertEqual(form.property('address'), '192.0.2.6')
            self.assertEqual(form.property('netmask'), '255.255.255.0')
            self.assertEqual(form.property('gateway'), '')
            self.assertEqual(form.property('dns'), '')
            applied = []
            form.applyRequested.connect(lambda *args: applied.append(args))
            form.apply()
            self.assertEqual(applied, [('static', '192.0.2.6', '255.255.255.0', '', '')])
        finally:
            sip.delete(form)
            sip.delete(engine)
