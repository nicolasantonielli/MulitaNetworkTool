import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from tests.qt_support import qt_app
from PyQt5.QtCore import QObject
from PyQt5.QtTest import QTest

from mulita.adapters.settings_store import JsonSettingsStore
from mulita.bootstrap import build_services
from mulita.config import AppConfig
from mulita.core.models import CommandResult
from mulita.core.platform import UsbDrive
from mulita.services.files import CaptureFilesService
from mulita.ui.qt.app import QtApplication
from tests.fakes import FakeRunner, FakeStorage


class ActivityLogTest(unittest.TestCase):
    def test_operator_can_record_review_and_pause_without_losing_history(self):
        # El proceso de la aplicación es dueño del singleton Qt y de su portapapeles.
        if __name__ != '__main__':
            subprocess.run([sys.executable, '-m', 'tests.test_activity_log'], check=True, timeout=60)
            return
        with tempfile.TemporaryDirectory() as folder:
            config = AppConfig(test_mode=True, capture_dir=Path(folder) / 'captures',
                               settings_path=Path(folder) / 'settings.json')
            runner = FakeRunner({'/usr/bin/ip': CommandResult(0, '[]'),
                                 '/usr/bin/nmcli': CommandResult(0, '')})
            services = build_services(config, runner=runner)
            services.wifi.connect = Mock(return_value='lab')
            app = QtApplication(config, services)
            try:
                ctx = app.engine.rootContext()
                settings = ctx.contextProperty('settings')
                activity = ctx.contextProperty('activity')
                ping = ctx.contextProperty('ping')
                self.assertFalse(settings.activityLogging)
                self.assertEqual(activity.days, [])
                self.assertFalse((config.capture_dir / 'actividad').exists())

                settings.setActivityLogging(True)
                self.assertTrue(JsonSettingsStore(config.settings_path).load().activity_logging)
                self.assertTrue(ping.start('192.0.2.10', 1, 1, 64))
                runner.handles[-1].finish()
                ctx.contextProperty('wifi').connectTo('lab', 'private-test-password', True)
                for _ in range(100):
                    QTest.qWait(20)
                    if 'lab | Completado' in activity.read(activity.days[0]):
                        break
                pager = app.root.findChild(QObject, 'homePager')
                home = pager.parentItem()
                tile = next(tile for tile in home.property('catalog').toVariant() if tile['id'] == 'activity')
                home.open.emit(tile['page'])
                app.app.processEvents()
                page = app.root.findChild(QObject, 'activityPage')
                self.assertTrue(page.isVisible())
                report = page.property('report')
                copy_button = next(child for child in page.findChildren(QObject) if child.property('text') == 'Copiar'
                                   and child.metaObject().indexOfSignal(b'clicked()') >= 0)
                copy_button.clicked.emit()
                self.assertEqual(app.app.clipboard().text(), report)
                self.assertIn('Ping | 192.0.2.10 | Inicio', report)
                self.assertIn('Ping | 192.0.2.10 | Finalizado', report)
                self.assertIn('lab | Completado', report)
                self.assertNotIn('private-test-password', report)
                self.assertEqual(services.files.list_files()[0].place, 'actividad')

                settings.setActivityLogging(False)
                self.assertFalse(JsonSettingsStore(config.settings_path).load().activity_logging)
                self.assertTrue(ping.start('198.51.100.1', 1, 1, 64))
                runner.handles[-1].finish()
                app.app.processEvents()
                self.assertEqual(activity.read(activity.days[0]), report)
                day = activity.days[0]
                filename = day + '.log'
                usb = Path(folder) / 'usb'
                usb.mkdir()
                files = CaptureFilesService(config.capture_dir, storage=FakeStorage((UsbDrive('sda1', 'USB', str(usb)),)))
                files.export('actividad', filename, 'sda1')
                self.assertEqual((usb / filename).read_text(encoding='utf-8'), report)

                history = config.capture_dir / 'actividad'
                (history / '2020-01-01.log').write_text('Previous session', encoding='utf-8')
                self.assertEqual(activity.days, [day, '2020-01-01'])
                page.setProperty('selectedDay', '2020-01-01')
                page.refresh()
                self.assertEqual(page.property('report'), 'Previous session')
            finally:
                app.dispose()


if __name__ == '__main__':
    unittest.main()
