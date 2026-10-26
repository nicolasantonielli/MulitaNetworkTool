import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.qt_support import qt_app
from PyQt5.QtCore import QCoreApplication, QEvent, QPointF, Qt, QUrl
from PyQt5.QtGui import QMouseEvent, QWindow
from PyQt5.QtQml import QQmlComponent, QQmlEngine
from PyQt5.QtQuick import QQuickWindow

from mulita.ui.qt.touch_debug import TouchDebug


class RecordingWindow(QWindow):
    def __init__(self):
        super().__init__()
        self.received = []

    def event(self, event):
        if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseMove):
            self.received.append((event.type(), event.localPos(), event.source()))
            return True
        return super().event(event)


class TouchInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        self.filter = TouchDebug()
        self.app.installEventFilter(self.filter)
        self.window = RecordingWindow()

    def tearDown(self):
        self.app.removeEventFilter(self.filter)
        self.window.close()

    def send(self, kind, x=30, y=30, source=Qt.MouseEventSynthesizedByQt, window=None):
        button = Qt.NoButton if kind == QEvent.MouseMove else Qt.LeftButton
        buttons = Qt.NoButton if kind == QEvent.MouseButtonRelease else Qt.LeftButton
        pos = QPointF(x, y)
        event = QMouseEvent(kind, pos, pos, pos, button, buttons, Qt.NoModifier, source)
        QCoreApplication.sendEvent(window or self.window, event)

    def tap(self, **kwargs):
        self.send(QEvent.MouseButtonPress, **kwargs)
        self.send(QEvent.MouseButtonRelease, **kwargs)

    def test_fast_taps_in_same_position_are_all_delivered(self):
        with patch('mulita.ui.qt.touch_debug.time.monotonic', return_value=10):
            for _ in range(5):
                self.tap()
        self.assertEqual(len(self.window.received), 10)

    def test_nearby_keys_are_not_suppressed(self):
        self.tap(x=30)
        self.tap(x=60)
        self.assertEqual(len(self.window.received), 4)

    def test_real_mouse_drag_and_release_are_not_modified(self):
        source = Qt.MouseEventNotSynthesized
        self.send(QEvent.MouseButtonPress, source=source)
        self.send(QEvent.MouseMove, x=500, source=source)
        self.send(QEvent.MouseButtonRelease, x=500, source=source)
        self.assertEqual([pos.x() for _, pos, _ in self.window.received], [30, 500, 500])

    def test_touch_drag_keeps_the_actual_release_position(self):
        self.send(QEvent.MouseButtonPress)
        self.send(QEvent.MouseMove, x=100)
        self.send(QEvent.MouseButtonRelease, x=120)
        self.assertEqual(self.window.received[-1][1].x(), 120)

    def test_release_jump_uses_last_valid_drag_position_and_preserves_source(self):
        self.send(QEvent.MouseButtonPress)
        self.send(QEvent.MouseMove, x=100)
        self.send(QEvent.MouseButtonRelease, x=900)
        self.assertEqual(self.window.received[-1], (
            QEvent.MouseButtonRelease, QPointF(100, 30), Qt.MouseEventSynthesizedByQt))
        self.tap(x=100)
        self.assertEqual(len(self.window.received), 5)

    def test_impossible_move_does_not_poison_following_release(self):
        self.send(QEvent.MouseButtonPress)
        self.send(QEvent.MouseMove, x=900)
        self.send(QEvent.MouseButtonRelease)
        self.assertEqual(len(self.window.received), 2)

    def test_raw_touch_logging_cannot_suppress_following_tap(self):
        point = SimpleNamespace(screenPos=lambda: QPointF(30, 30),
                                state=lambda: Qt.TouchPointPressed, id=lambda: 0)
        event = SimpleNamespace(touchPoints=lambda: [point])
        self.tap()
        for _ in range(10):
            self.assertFalse(self.filter._touch(self.window, event, 'begin'))
        self.tap()
        self.assertEqual(len(self.window.received), 4)

    def test_qml_button_receives_repeated_touch_taps(self):
        engine = QQmlEngine()
        component = QQmlComponent(engine)
        qml = '''import QtQuick 2.15
import "../mulita/ui/qt/qml/components"
Rectangle {
    width: 200; height: 100
    property int hits: 0
    QtObject {
        id: ui
        property real mm: 4
        property int touch: 40
        property int padding: 8
        property int gap: 4
        property int radius: 4
        property int icon: 16
        property int fontBody: 12
        property color primary: "blue"
        property color success: "green"
        property color danger: "red"
        property color warning: "yellow"
        property color surfaceHigh: "gray"
        property color text: "black"
        property color onAccent: "white"
        property color border: "gray"
    }
    TouchButton { width: 150; height: 80; text: "Test"; onClicked: parent.hits++ }
}'''
        component.setData(qml.encode(), QUrl.fromLocalFile(str(Path(__file__).resolve())))
        self.assertEqual(component.errors(), [])
        root = component.create()
        self.assertIsNotNone(root)
        window = QQuickWindow()
        window.resize(200, 100)
        root.setParentItem(window.contentItem())
        window.show()
        self.app.processEvents()
        try:
            for _ in range(5):
                self.tap(window=window)
                self.app.processEvents()
            self.assertEqual(root.property('hits'), 5)
        finally:
            window.close()
            root.setParentItem(None)


if __name__ == '__main__':
    unittest.main()
