import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.qt_support import qt_app
from PyQt5.QtCore import QCoreApplication, QEvent, QPointF, Qt, QUrl
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtQml import QQmlComponent, QQmlEngine
from PyQt5.QtQuick import QQuickWindow

from mulita.adapters.settings_store import MemorySettingsStore
from mulita.config import AppConfig
from mulita.services.settings import SettingsService
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.system import Appearance, I18nController
from mulita.ui.qt.touch_debug import TouchDebug
from mulita.ui.qt.touch_test import TouchTest
from tests.test_touch import RecordingWindow


class TouchPanelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        self.monitor = TouchTest()
        self.window = RecordingWindow()

    def tearDown(self):
        self.window.close()

    def event(self, kind=QEvent.MouseButtonPress, x=30):
        point = QPointF(x, 30)
        button = Qt.NoButton if kind == QEvent.MouseMove else Qt.LeftButton
        buttons = Qt.NoButton if kind == QEvent.MouseButtonRelease else Qt.LeftButton
        return QMouseEvent(kind, point, point, point, button, buttons,
                           Qt.NoModifier, Qt.MouseEventSynthesizedByQt)

    def test_inactive_monitor_records_nothing_and_cannot_bypass(self):
        self.monitor.observe(self.window, self.event())
        self.monitor.setBypass(True)
        self.assertEqual(self.monitor.events, [])
        self.assertFalse(self.monitor.bypass)

    def test_counts_keep_repeated_events_and_clear_resets_everything(self):
        self.monitor.setActive(True)
        for _ in range(250):
            self.monitor.observe(self.window, self.event())
        self.assertEqual(self.monitor.counts['mouse_down'], 250)
        self.assertEqual(len(self.monitor.events), 200)
        self.assertEqual(self.monitor.latest['source'], 'qt')
        self.monitor.clear()
        self.assertEqual(self.monitor.counts, {})
        self.assertEqual(self.monitor.events, [])
        self.assertEqual(self.monitor.latest, {})

    def test_raw_touch_and_mouse_have_separate_counts(self):
        self.monitor.setActive(True)
        point = SimpleNamespace(screenPos=lambda: QPointF(100, 50),
                                state=lambda: Qt.TouchPointPressed, id=lambda: 2)
        touch = SimpleNamespace(type=lambda: QEvent.TouchBegin, touchPoints=lambda: [point])
        self.monitor.observe(self.window, touch)
        self.monitor.observe(self.window, self.event())
        self.assertEqual(self.monitor.counts, {'touch_down': 1, 'mouse_down': 1})
        self.assertEqual(self.monitor.events[0]['id'], 2)
        self.assertEqual(self.monitor.events[0]['source'], 'touch')

    def test_cancel_without_points_is_visible(self):
        self.monitor.setActive(True)
        cancel = SimpleNamespace(type=lambda: QEvent.TouchCancel, touchPoints=lambda: [])
        self.monitor.observe(self.window, cancel)
        self.assertEqual(self.monitor.counts['touch_cancel'], 1)
        self.assertEqual(self.monitor.latest['phase'], 'cancel')

    def test_monitor_observes_rejected_moves_and_bypass_is_scoped_to_page(self):
        filter_ = TouchDebug(self.monitor)
        self.app.installEventFilter(filter_)
        self.monitor.setActive(True)
        try:
            QCoreApplication.sendEvent(self.window, self.event())
            QCoreApplication.sendEvent(self.window, self.event(QEvent.MouseMove, 900))
            self.assertEqual(len(self.window.received), 1)
            self.assertEqual(self.monitor.latest['x'], 900)
            self.monitor.setBypass(True)
            QCoreApplication.sendEvent(self.window, self.event(QEvent.MouseMove, 900))
            self.assertEqual(len(self.window.received), 2)
            self.monitor.setActive(False)
            self.assertFalse(self.monitor.bypass)
            QCoreApplication.sendEvent(self.window, self.event())
            QCoreApplication.sendEvent(self.window, self.event(QEvent.MouseMove, 900))
            self.assertEqual(len(self.window.received), 3)
        finally:
            self.app.removeEventFilter(filter_)

    def test_qml_page_loads_counts_clicks_clears_and_restores_normal_on_exit(self):
        light = SimpleNamespace(apply=lambda _: None, available=lambda: False)
        settings = SettingsService(MemorySettingsStore(), light)
        ctx = BridgeContext(AppConfig(test_mode=True), SimpleNamespace(settings=settings),
                            None, Notifier())
        appearance = Appearance(ctx)
        i18n = I18nController(ctx)
        engine = QQmlEngine()
        engine.rootContext().setContextProperty('ui', appearance)
        engine.rootContext().setContextProperty('i18n', i18n)
        engine.rootContext().setContextProperty('touchTest', self.monitor)
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(
            Path('mulita/ui/qt/qml/pages/TouchTestPage.qml').resolve())))
        self.assertEqual([error.toString() for error in component.errors()], [])
        page = component.create()
        self.assertIsNotNone(page)
        window = QQuickWindow()
        window.resize(540, 390)
        page.setWidth(540)
        page.setHeight(390)
        page.setParentItem(window.contentItem())
        window.show()
        self.app.processEvents()
        try:
            surface = page.findChild(type(page), 'touchTestSurface')
            self.assertIsNotNone(surface)
            self.assertGreaterEqual(surface.height(), appearance.touch)
            self.assertLessEqual(surface.y() + surface.height(), page.height())
            position = surface.mapToScene(QPointF(surface.width() / 2, surface.height() / 2))
            for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
                event = QMouseEvent(kind, position, position, window.mapToGlobal(position.toPoint()),
                                    Qt.LeftButton, Qt.LeftButton if kind == QEvent.MouseButtonPress
                                    else Qt.NoButton, Qt.NoModifier)
                QCoreApplication.sendEvent(window, event)
            self.assertEqual(page.property('taps'), 1)
            self.assertTrue(self.monitor.active)
            self.monitor.setBypass(True)
            QCoreApplication.sendEvent(self.window, self.event())
            page.reset()
            self.assertEqual(page.property('taps'), 0)
            self.assertEqual(self.monitor.events, [])
            page.setVisible(False)
            self.assertFalse(self.monitor.active)
            self.assertFalse(self.monitor.bypass)
        finally:
            window.close()
            page.setParentItem(None)


if __name__ == '__main__':
    unittest.main()
