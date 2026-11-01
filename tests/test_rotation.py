from pathlib import Path
import tempfile
import unittest

from PyQt5.QtCore import QObject, QPointF, Qt, QUrl
from PyQt5.QtQml import QQmlComponent, QQmlEngine
from PyQt5.QtQuick import QQuickWindow
from PyQt5.QtTest import QTest

from tests.qt_support import qt_app
from mulita.adapters.settings_store import JsonSettingsStore
from mulita.core.errors import ValidationError
from mulita.core.settings import settings_from_dict
from mulita.services.settings import SettingsService


class RotationSettingsTest(unittest.TestCase):
    def test_four_angles_persist_and_keep_other_display_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            store = JsonSettingsStore(Path(folder) / 'settings.json')
            service = SettingsService(store)
            service.set_scale(1.1)
            service.set_resize_tiles(False)
            for angle in (0, 90, 180, 270):
                service.set_rotation(angle)
                display = store.load().display
                self.assertEqual(display.rotation, angle)
                self.assertEqual(display.ui_scale, 1.1)
                self.assertFalse(display.resize_tiles)

    def test_invalid_angles_are_rejected_and_old_settings_default_to_zero(self):
        self.assertEqual(settings_from_dict({}).display.rotation, 0)
        for angle in (-90, 360, 45, '90', True, None):
            self.assertEqual(settings_from_dict({'rotation': angle}).display.rotation, 0)
            with tempfile.TemporaryDirectory() as folder:
                service = SettingsService(JsonSettingsStore(Path(folder) / 'settings.json'))
                with self.assertRaises(ValidationError):
                    service.set_rotation(angle)


class RotationInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def test_controls_receive_clicks_at_rotated_coordinates_in_all_orientations(self):
        engine = QQmlEngine()
        component = QQmlComponent(engine)
        component.setData(b'''import QtQuick 2.15
import "../mulita/ui/qt/qml/components"
RotatedSurface {
    property int hits: 0
    Rectangle {
        objectName: "target"
        x: 40; y: 70; width: 100; height: 50
        MouseArea { anchors.fill: parent; onClicked: parent.parent.hits++ }
    }
}''', QUrl.fromLocalFile(str(Path(__file__).resolve())))
        self.assertEqual(component.errors(), [])
        root = component.create()
        self.assertIsNotNone(root)
        window = QQuickWindow()
        window.resize(800, 480)
        root.setParentItem(window.contentItem())
        window.show()
        try:
            target = root.findChild(QObject, 'target')
            for index, angle in enumerate((0, 90, 180, 270)):
                root.setProperty('angle', angle)
                self.app.processEvents()
                expected = (480, 800) if angle in (90, 270) else (800, 480)
                self.assertEqual((root.width(), root.height()), expected)
                point = target.mapToScene(QPointF(50, 25)).toPoint()
                self.assertTrue(0 <= point.x() < 800 and 0 <= point.y() < 480)
                QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
                self.assertEqual(root.property('hits'), index + 1)
        finally:
            root.setParentItem(None)
            window.close()
            from PyQt5 import sip
            sip.delete(root)
