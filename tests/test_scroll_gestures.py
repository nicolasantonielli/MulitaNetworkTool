import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.qt_support import qt_app
from PyQt5.QtCore import QObject, QPoint, Qt, QUrl
from PyQt5.QtQml import QQmlComponent, QQmlEngine
from PyQt5.QtQuick import QQuickWindow
from PyQt5.QtTest import QTest

from mulita.adapters.settings_store import MemorySettingsStore
from mulita.config import AppConfig
from mulita.services.settings import SettingsService
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.system import Appearance
from mulita.ui.qt.touch_debug import TouchDebug


class ScrollGestureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        light = SimpleNamespace(apply=lambda _: None, available=lambda: False)
        services = SimpleNamespace(settings=SettingsService(MemorySettingsStore(), light))
        self.ui = Appearance(BridgeContext(AppConfig(test_mode=True), services, None, Notifier()))
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty('ui', self.ui)
        self.filter = TouchDebug()
        self.app.installEventFilter(self.filter)

    def tearDown(self):
        self.app.removeEventFilter(self.filter)
        self.window.close()
        self.root.setParentItem(None)

    def load(self, content):
        qml = '''import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../mulita/ui/qt/qml/components"
Item {
    id: root
    width: 400; height: 260
    property int hits: 0
''' + content + '\n}'
        self.component = QQmlComponent(self.engine)
        self.component.setData(qml.encode(), QUrl.fromLocalFile(str(Path(__file__).resolve())))
        self.assertEqual([e.toString() for e in self.component.errors()], [])
        self.root = self.component.create()
        self.assertIsNotNone(self.root)
        self.window = QQuickWindow()
        self.window.resize(400, 260)
        self.root.setParentItem(self.window.contentItem())
        self.window.show()
        QTest.qWait(30)

    def swipe(self, start, end):
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, start)
        for step in range(1, 9):
            point = start + (end - start) * (step / 8)
            QTest.mouseMove(self.window, point, 16)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, end)
        self.app.processEvents()

    def load_scroll_page(self):
        self.load('''
    ScrollPage {
        objectName: "page"
        anchors.fill: parent
        TouchButton {
            Layout.fillWidth: true
            implicitHeight: 200
            text: "Test"
            onClicked: root.hits++
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 800 }
    }
''')
        page = self.root.findChild(QObject, 'page')
        return next(child for child in page.childItems() if child.property('contentY') is not None)

    def test_swipe_over_button_scrolls_without_clicking_and_can_reverse(self):
        flick = self.load_scroll_page()
        self.swipe(QPoint(150, 170), QPoint(150, 30))
        self.assertGreater(flick.property('contentY'), 40)
        self.assertEqual(self.root.property('hits'), 0)
        flick.cancelFlick()
        flick.setProperty('contentY', 250)
        self.swipe(QPoint(150, 40), QPoint(150, 200))
        self.assertLess(flick.property('contentY'), 210)
        self.assertEqual(self.root.property('hits'), 0)

    def test_stationary_tap_inside_scroll_page_still_clicks(self):
        flick = self.load_scroll_page()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(150, 80))
        self.app.processEvents()
        self.assertEqual(self.root.property('hits'), 1)
        self.assertEqual(flick.property('contentY'), 0)

    def test_fast_drag_out_and_back_is_not_a_button_click(self):
        self.load('TouchButton { width: 400; height: 260; text: "Test"; onClicked: root.hits++ }')
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(100, 100))
        QTest.mouseMove(self.window, QPoint(100, 180), 16)
        QTest.mouseMove(self.window, QPoint(100, 100), 16)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(100, 100))
        self.assertEqual(self.root.property('hits'), 0)

    def test_list_delegates_allow_swiping_without_selecting(self):
        self.load('''
    ListView {
        objectName: "list"
        anchors.fill: parent
        model: 30
        boundsBehavior: Flickable.StopAtBounds
        delegate: Rectangle {
            width: 400; height: 60
            TouchArea { onTapped: root.hits++ }
        }
    }
''')
        view = self.root.findChild(QObject, 'list')
        self.swipe(QPoint(150, 200), QPoint(150, 40))
        self.assertGreater(view.property('contentY'), 40)
        self.assertEqual(self.root.property('hits'), 0)


if __name__ == '__main__':
    unittest.main()
