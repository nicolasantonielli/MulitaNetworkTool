import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.qt_support import qt_app
from PyQt5.QtCore import QObject, QEvent, QPoint, QPointF, Qt, QUrl
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import QQmlComponent, QQmlEngine
from PyQt5.QtTest import QTest

from mulita.adapters.settings_store import MemorySettingsStore
from mulita.config import AppConfig
from mulita.presentation.i18n import tr
from mulita.services.settings import SettingsService
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.system import Appearance, I18nController, SystemController
from mulita.ui.qt.text_copy import TextCopyController


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
        self.i18n = I18nController(ctx)
        self.copy = TextCopyController()
        self.app.installEventFilter(self.copy)
        self.engine = QQmlEngine()
        for name, value in [('ui', self.ui), ('system', self.system), ('i18n', self.i18n),
                            ('textCopy', self.copy), ('testValue', VALUE)]:
            self.engine.rootContext().setContextProperty(name, value)
        self.component = QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../mulita/ui/qt/qml/components"
ApplicationWindow {
    width: 440; height: 400; visible: true
    ScrollPage {
        objectName: "table"
        width: 220; height: 260
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
    }
    Field { objectName: "field"; x: 240; y: 20; width: 190; text: "abcdefghijklmnop" }
    TextEdit {
        objectName: "output"
        x: 240; y: 110; width: 190; height: 60
        text: "output text"; selectByMouse: true; readOnly: true
        font.pixelSize: 18
    }
    Text { x: 240; y: 210; text: "Informative label"; font.pixelSize: 18 }
    TouchButton { x: 240; y: 300; text: "Action" }
    CopyMenu { }
}''', QUrl.fromLocalFile(str(Path(__file__).resolve())))
        self.assertEqual([e.toString() for e in self.component.errors()], [])
        self.window = self.component.create()
        self.assertIsNotNone(self.window)
        QTest.qWait(30)
        self.menu = self.window.findChild(QObject, 'textCopyMenu')
        QGuiApplication.clipboard().setText('unchanged')

    def tearDown(self):
        self.app.removeEventFilter(self.copy)
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def hold(self, position):
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, position)
        QTest.qWait(700)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, position)
        QTest.qWait(20)

    def choose_copy(self):
        action = self.menu.property('contentItem')
        position = action.mapToScene(QPointF(action.width() / 2, action.height() / 2)).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, position)
        QTest.qWait(20)

    def assert_pending(self, value):
        self.assertTrue(self.menu.property('opened'))
        self.assertEqual(self.menu.property('value'), value)
        self.assertEqual(QGuiApplication.clipboard().text(), 'unchanged')
        self.assertEqual(self.toasts, [])

    def test_hold_opens_menu_and_only_copy_action_changes_clipboard(self):
        self.hold(QPoint(80, 25))
        self.assert_pending(VALUE)
        self.choose_copy()
        self.assertFalse(self.menu.property('opened'))
        self.assertEqual(QGuiApplication.clipboard().text(), VALUE)
        self.assertEqual(self.toasts, [('success', tr('copy'), tr('textCopied'))])

    def test_outside_press_dismisses_without_copying_or_reopening(self):
        self.hold(QPoint(80, 25))
        self.assert_pending(VALUE)
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(410, 380))
        QTest.qWait(30)
        self.assertFalse(self.menu.property('opened'))
        self.assertFalse(self.copy.menuVisible)
        self.assertEqual(QGuiApplication.clipboard().text(), 'unchanged')
        self.assertEqual(self.toasts, [])

    def test_right_click_opens_same_menu_without_copying(self):
        QTest.mouseClick(self.window, Qt.RightButton, Qt.NoModifier, QPoint(80, 25))
        QTest.qWait(20)
        self.assert_pending(VALUE)

    def test_tap_does_not_open_menu(self):
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(80, 25))
        QTest.qWait(20)
        self.assertFalse(self.menu.property('opened'))
        self.assertEqual(QGuiApplication.clipboard().text(), 'unchanged')

    def test_swipe_scrolls_without_opening_menu(self):
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(80, 200))
        for y in range(180, 39, -20):
            QTest.mouseMove(self.window, QPoint(80, y), 16)
        QTest.qWait(700)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(80, 40))
        table = self.window.findChild(QObject, 'table')
        flick = next(child for child in table.childItems() if child.property('contentY') is not None)
        self.assertGreater(flick.property('contentY'), 40)
        self.assertFalse(self.menu.property('opened'))
        self.assertEqual(QGuiApplication.clipboard().text(), 'unchanged')

    def test_hold_on_plain_label_uses_same_menu(self):
        self.hold(QPoint(275, 220))
        self.assert_pending('Informative label')

    def test_hold_on_text_field_uses_same_menu(self):
        self.hold(QPoint(270, 45))
        field = self.window.findChild(QObject, 'field')
        self.assert_pending(field.property('selectedText') or field.property('text'))

    def test_mouse_selection_release_opens_menu_for_selected_text(self):
        editor = self.window.findChild(QObject, 'output')
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(241, 120))
        for x in range(250, 320, 10):
            QTest.mouseMove(self.window, QPoint(x, 120), 16)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(320, 120))
        QTest.qWait(20)
        selected = editor.property('selectedText')
        self.assertTrue(selected)
        self.assert_pending(selected)
        self.choose_copy()
        self.assertEqual(QGuiApplication.clipboard().text(), selected)

    def test_hold_on_action_button_does_not_open_copy_menu(self):
        self.hold(QPoint(280, 325))
        self.assertFalse(self.menu.property('opened'))
        self.assertEqual(QGuiApplication.clipboard().text(), 'unchanged')

    def test_password_field_does_not_expose_secret_in_copy_menu(self):
        field = self.window.findChild(QObject, 'field')
        field.setProperty('echoMode', 2)
        self.hold(QPoint(270, 45))
        self.assertFalse(self.menu.property('opened'))
        self.assertEqual(QGuiApplication.clipboard().text(), 'unchanged')

    def test_field_selection_opens_menu_without_automatic_copy(self):
        field = self.window.findChild(QObject, 'field')
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(265, 45))
        for x in range(275, 385, 10):
            QTest.mouseMove(self.window, QPoint(x, 45), 16)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(385, 45))
        QTest.qWait(20)
        selected = field.property('selectedText')
        self.assertTrue(selected)
        self.assert_pending(selected)

    def test_pressing_another_cell_dismisses_without_copying(self):
        self.hold(QPoint(80, 25))
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(80, 200))
        QTest.qWait(30)
        self.assertFalse(self.menu.property('opened'))
        self.assertEqual(QGuiApplication.clipboard().text(), 'unchanged')

    def test_escape_dismisses_without_copying(self):
        self.hold(QPoint(80, 25))
        QTest.keyClick(self.window, Qt.Key_Escape)
        QTest.qWait(30)
        self.assertFalse(self.menu.property('opened'))
        self.assertEqual(QGuiApplication.clipboard().text(), 'unchanged')

    def test_raw_touch_hold_opens_menu_without_copying(self):
        local = QPointF(80, 25)
        screen = self.window.mapToGlobal(local.toPoint())
        point = SimpleNamespace(pos=lambda: local, screenPos=lambda: QPointF(screen))
        event = SimpleNamespace(type=lambda: QEvent.TouchBegin, touchPoints=lambda: [point])
        self.assertFalse(self.copy.eventFilter(self.window, event))
        QTest.qWait(700)
        self.assert_pending(VALUE)

    def test_multitouch_end_without_points_does_not_block_next_mouse_hold(self):
        begin = SimpleNamespace(type=lambda: QEvent.TouchBegin, touchPoints=lambda: [None, None])
        end = SimpleNamespace(type=lambda: QEvent.TouchEnd, touchPoints=lambda: [])
        self.copy.eventFilter(self.window, begin)
        self.copy.eventFilter(self.window, end)
        self.hold(QPoint(80, 25))
        self.assert_pending(VALUE)


if __name__ == '__main__':
    unittest.main()
