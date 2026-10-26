import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.qt_support import qt_app
from PyQt5.QtCore import QPoint, Qt, QUrl
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import QQmlComponent, QQmlEngine
from PyQt5.QtQuick import QQuickWindow
from PyQt5.QtTest import QTest

from mulita.adapters.settings_store import MemorySettingsStore
from mulita.config import AppConfig
from mulita.presentation.i18n import tr
from mulita.services.settings import SettingsService
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.system import Appearance, SystemController


VALUE = '2001:db8:1234:5678:abcd:ef01:2345:6789 <servicio completo>'


class TableCopyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        light = SimpleNamespace(apply=lambda _: None, available=lambda: False)
        services = SimpleNamespace(settings=SettingsService(MemorySettingsStore(), light))
        self.notifier = Notifier()
        self.toasts = []
        self.notifier.notified.connect(lambda *args: self.toasts.append(args))
        ctx = BridgeContext(AppConfig(test_mode=True), services, None, self.notifier)
        self.ui = Appearance(ctx)
        self.system = SystemController(ctx)
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty('ui', self.ui)
        self.engine.rootContext().setContextProperty('system', self.system)
        self.engine.rootContext().setContextProperty('testValue', VALUE)
        self.component = QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../mulita/ui/qt/qml/components"
ScrollPage {
    width: 240; height: 260
    Repeater {
        model: 20
        CopyableCell {
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            text: testValue
            color: ui.text
            font.pixelSize: ui.fontSmall
            elide: Text.ElideRight
        }
    }
}''', QUrl.fromLocalFile(str(Path(__file__).resolve())))
        self.assertEqual([e.toString() for e in self.component.errors()], [])
        self.root = self.component.create()
        self.assertIsNotNone(self.root)
        self.window = QQuickWindow()
        self.window.resize(240, 260)
        self.root.setParentItem(self.window.contentItem())
        self.window.show()
        QTest.qWait(30)
        QGuiApplication.clipboard().setText('unchanged')

    def tearDown(self):
        self.window.close()
        self.root.setParentItem(None)

    def test_hold_copies_full_elided_value_and_confirms_with_toast(self):
        position = QPoint(80, 25)
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, position)
        QTest.qWait(700)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, position)
        self.assertEqual(QGuiApplication.clipboard().text(), VALUE)
        self.assertEqual(self.toasts, [('success', tr('copy'), tr('textCopied'))])

    def test_tap_does_not_overwrite_clipboard(self):
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(80, 25))
        self.assertEqual(QGuiApplication.clipboard().text(), 'unchanged')
        self.assertEqual(self.toasts, [])

    def test_vertical_swipe_scrolls_without_copying_even_if_held_after_moving(self):
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(80, 200))
        for y in range(180, 39, -20):
            QTest.mouseMove(self.window, QPoint(80, y), 16)
        QTest.qWait(700)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(80, 40))
        flick = next(child for child in self.root.childItems() if child.property('contentY') is not None)
        self.assertGreater(flick.property('contentY'), 40)
        self.assertEqual(QGuiApplication.clipboard().text(), 'unchanged')
        self.assertEqual(self.toasts, [])

    def test_right_click_copies_value(self):
        QTest.mouseClick(self.window, Qt.RightButton, Qt.NoModifier, QPoint(80, 25))
        self.assertEqual(QGuiApplication.clipboard().text(), VALUE)

    def test_empty_value_does_not_overwrite_clipboard_or_show_toast(self):
        self.system.copyText('')
        self.assertEqual(QGuiApplication.clipboard().text(), 'unchanged')
        self.assertEqual(self.toasts, [])


if __name__ == '__main__':
    unittest.main()
