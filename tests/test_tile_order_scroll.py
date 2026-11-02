import unittest
from pathlib import Path
from PyQt5 import sip
from PyQt5.QtCore import QObject, QPointF, Qt, QUrl
from PyQt5.QtQml import QQmlComponent, QQmlEngine
from PyQt5.QtQuick import QQuickWindow
from PyQt5.QtTest import QTest
from tests.qt_support import qt_app
from tests.fakes import FakeBacklight
from mulita.adapters.settings_store import MemorySettingsStore
from mulita.config import AppConfig
from mulita.services.settings import SettingsService
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.system import Appearance, I18nController, SettingsController


class TileOrderScrollTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def test_release_keeps_the_preview_position(self):
        cases = [
            ('down_one', 1, 2, [[1, 0, 2], [3, 4, 5]]),
            ('down_to_last', 1, 3, [[1, 2, 0], [3, 4, 5]]),
            ('up', 3, 1, [[2, 0, 1], [3, 4, 5]]),
            ('unchanged', 2, 2, [[0, 1, 2], [3, 4, 5]]),
            ('down_across_screens', 1, 5, [[1, 2], [3, 0, 4, 5]]),
            ('up_across_screens', 5, 2, [[0, 3, 1, 2], [4, 5]]),
            ('to_separator', 1, 4, [[1, 2], [0, 3, 4, 5]]),
        ]
        for name, start_line, target_line, expected in cases:
            with self.subTest(name=name):
                service = SettingsService(MemorySettingsStore(), FakeBacklight())
                tiles = [tile for page in service.current.home.screens for tile in page]
                screens = [tiles[i:i + 3] for i in range(0, len(tiles), 3)]
                service.set_home_screens(screens)
                ctx = BridgeContext(AppConfig(test_mode=True), service, None, Notifier())
                controllers = {'ui': Appearance(ctx), 'i18n': I18nController(ctx),
                               'settings': SettingsController(ctx)}
                engine = QQmlEngine()
                for key, controller in controllers.items():
                    engine.rootContext().setContextProperty(key, controller)
                component = QQmlComponent(engine)
                path = Path(__file__).resolve().parents[1] / 'mulita/ui/qt/qml/pages/TileOrderPage.qml'
                component.loadUrl(QUrl.fromLocalFile(str(path)))
                self.assertEqual(component.errors(), [])
                root = component.create()
                window = QQuickWindow()
                window.resize(640, 1000)
                root.setWidth(640)
                root.setHeight(1000)
                root.setParentItem(window.contentItem())
                window.show()
                try:
                    QTest.qWait(40)
                    flick = root.findChild(QObject, 'orderFlick')
                    row_h = root.property('rowH')
                    start = flick.mapToScene(QPointF(100, row_h * (start_line + 0.5))).toPoint()
                    target = flick.mapToScene(QPointF(100, row_h * (target_line + 0.5))).toPoint()
                    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
                    self.assertTrue(root.property('dragging'))
                    QTest.mouseMove(window, target, 20)
                    self.assertEqual(root.property('hover'), target_line)
                    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, target)
                    wanted = tuple(tuple(tiles[i] for i in page) for page in expected)
                    wanted += tuple(tuple(page) for page in screens[2:])
                    self.assertEqual(service.current.home.screens, wanted)
                    self.assertFalse(root.property('dragging'))
                finally:
                    window.close()
                    sip.delete(root)
                    sip.delete(window)
                    sip.delete(engine)

    def test_held_row_scrolls_both_edges_updates_target_and_stops_on_release(self):
        service = SettingsService(MemorySettingsStore(), FakeBacklight())
        tiles = [tile for page in service.current.home.screens for tile in page]
        service.set_home_screens([tiles[i:i + 2] for i in range(0, len(tiles), 2)])
        ctx = BridgeContext(AppConfig(test_mode=True), service, None, Notifier())
        controllers = {'ui': Appearance(ctx), 'i18n': I18nController(ctx), 'settings': SettingsController(ctx)}
        engine = QQmlEngine()
        for name, controller in controllers.items():
            engine.rootContext().setContextProperty(name, controller)
        component = QQmlComponent(engine)
        path = Path(__file__).resolve().parents[1] / 'mulita/ui/qt/qml/pages/TileOrderPage.qml'
        component.loadUrl(QUrl.fromLocalFile(str(path)))
        self.assertEqual(component.errors(), [])
        root = component.create()
        window = QQuickWindow()
        window.resize(640, 300)
        root.setWidth(640); root.setHeight(300)
        root.setParentItem(window.contentItem())
        window.show()
        try:
            QTest.qWait(40)
            flick = root.findChild(QObject, 'orderFlick')
            def point(y):
                return flick.mapToScene(QPointF(100, y)).toPoint()
            start = point(root.property('rowH') * 1.5)
            bottom = point(flick.height() - 2)
            top = point(2)
            QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
            self.assertTrue(root.property('dragging'))
            QTest.mouseMove(window, bottom, 20)
            hover = root.property('hover')
            QTest.qWait(650)
            down = flick.property('contentY')
            self.assertGreater(down, 40)
            self.assertGreater(root.property('hover'), hover)
            # The dragged card stays under a stationary pointer while content moves.
            area = root.property('activeDrag')
            before = area.mapToScene(QPointF(0, 0)).y()
            QTest.qWait(100)
            self.assertAlmostEqual(area.mapToScene(QPointF(0, 0)).y(), before, delta=2)
            QTest.mouseMove(window, top, 20)
            QTest.qWait(500)
            self.assertLess(flick.property('contentY'), down)
            QTest.mouseMove(window, bottom, 20)
            QTest.qWait(700)
            target = root.property('hover')
            self.assertGreater(target, hover)
            QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, bottom)
            self.assertNotIn(tiles[0], service.current.home.screens[0])
            self.assertCountEqual([tile for page in service.current.home.screens for tile in page], tiles)
            self.assertFalse(root.property('dragging'))
            self.assertIsNone(root.property('activeDrag'))
            stopped = flick.property('contentY')
            QTest.qWait(150)
            self.assertEqual(flick.property('contentY'), stopped)
        finally:
            window.close()
            sip.delete(root)
            sip.delete(window)
            sip.delete(engine)
