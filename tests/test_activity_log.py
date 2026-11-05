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
from mulita.core.events import OperationEvent
from mulita.core.platform import UsbDrive
from mulita.services.files import CaptureFilesService
from mulita.ui.qt.app import QtApplication
from tests.fakes import FakeRunner, FakeStorage


class ActivityLogTest(unittest.TestCase):
    def load_journal(self, controller, day=''):
        controller.refresh(day)
        self.wait_journal(controller)
        return controller.report

    def wait_journal(self, controller):
        for _ in range(200):
            QTest.qWait(10)
            if not controller.busy:
                return
        self.fail('Journal did not finish loading')

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
            usb = Path(folder) / 'usb'
            usb.mkdir()
            services.files = CaptureFilesService(config.capture_dir, storage=FakeStorage((UsbDrive('sda1', 'USB', str(usb)),)))
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
                    if not activity.busy:
                        activity.refresh('')
                    QTest.qWait(20)
                    if activity.days and 'lab | Completado' in activity.read(activity.days[0]):
                        break
                pager = app.root.findChild(QObject, 'homePager')
                home = pager.parentItem()
                tile = next(tile for tile in home.property('catalog').toVariant() if tile['id'] == 'activity')
                home.open.emit(tile['page'])
                app.app.processEvents()
                page = app.root.findChild(QObject, 'activityPage')
                self.assertTrue(page.isVisible())
                self.wait_journal(activity)
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
                buttons = [child for child in page.findChildren(QObject) if child.property('text') == 'Exportar'
                           and child.metaObject().indexOfSignal(b'clicked()') >= 0]
                buttons[0].clicked.emit()
                for _ in range(100):
                    QTest.qWait(20)
                    if buttons[1].isVisible() and buttons[1].isEnabled():
                        break
                self.assertTrue(buttons[1].isEnabled())
                buttons[1].clicked.emit()
                for _ in range(100):
                    QTest.qWait(20)
                    if (usb / filename).exists():
                        break
                self.assertEqual((usb / filename).read_text(encoding='utf-8'), report)

                history = config.capture_dir / 'actividad'
                (history / '2020-01-01.log').write_text('Previous session', encoding='utf-8')
                self.load_journal(activity, day)
                self.assertEqual(activity.days, [day, '2020-01-01'])
                page.setProperty('selectedDay', '2020-01-01')
                page.refresh()
                self.wait_journal(activity)
                self.assertEqual(page.property('report'), 'Previous session')
                delete_button = next(child for child in page.findChildren(QObject) if child.property('text') == 'Borrar'
                                     and child.metaObject().indexOfSignal(b'clicked()') >= 0)
                delete_button.clicked.emit()
                QTest.qWait(300)
                dialog = next(child for child in page.findChildren(QObject) if child.property('opened') is True)
                dialog.finish(False)
                self.assertTrue((history / '2020-01-01.log').exists())
                delete_button.clicked.emit()
                dialog.finish(True)
                self.wait_journal(activity)
                self.assertEqual(activity.days, [day])
                self.assertEqual(page.property('report'), report)

                journal = ctx.contextProperty('technicalJournal')
                self.assertFalse(settings.technicalJournal)
                self.assertEqual(journal.days, [])
                settings.setTechnicalJournal(True)
                self.assertTrue(JsonSettingsStore(config.settings_path).load().technical_journal)
                (config.capture_dir / 'ping').mkdir(exist_ok=True)
                self.assertTrue(ping.start('8.8.8.8', 2, 1, 64))
                runner.outputs[-1]('2 packets transmitted, 1 received, 50% packet loss, time 1000ms\n'
                                   'rtt min/avg/max/mdev = 9.0/10.0/11.0/0.2 ms\n')
                runner.handles[-1].finish()
                app.app.processEvents()
                ping.save('ping')
                for _ in range(100):
                    QTest.qWait(20)
                    if not ping.saving:
                        break
                text = self.load_journal(journal, day)
                ping_cards = [entry for entry in journal.entries if entry['kind'] == 'Ping' and '8.8.8.8' in entry['text']]
                self.assertEqual(len(ping_cards), 1)
                self.assertIn('50%', ping_cards[0]['results'])
                self.assertIn(' - Se hizo ping a 8.8.8.8.', text)
                self.assertIn('se enviaron 2 paquetes y se recibió 1 (50% de pérdida)', text)
                self.assertIn('Tiempo medio de respuesta: 10.0 ms.', text)
                self.assertIn('Se exportó el archivo ping.csv.', text)
                self.assertIn('Se exportó el archivo ping.statics.csv.', text)
                self.assertEqual(text.count('Se hizo ping a 8.8.8.8.'), 1)
                self.assertEqual(text.count('Se exportó el archivo ping.csv.'), 1)
                self.assertEqual(activity.read(day), report)

                settings.setLanguage('en')
                self.assertTrue(ping.start('1.1.1.1', 2, 1, 64))
                runner.outputs[-1]('2 packets transmitted, 1 received, 50% packet loss, time 1000ms\n'
                                   'rtt min/avg/max/mdev = 9.0/10.0/11.0/0.2 ms\n')
                runner.handles[-1].finish()
                app.app.processEvents()
                ping.save('english')
                for _ in range(100):
                    QTest.qWait(20)
                    if not ping.saving:
                        break
                updated = self.load_journal(journal, day)
                self.assertTrue(updated.startswith(text))
                self.assertIn('A ping was sent to 1.1.1.1.', updated)
                self.assertIn('2 packets were sent and 1 was received (50% loss).', updated)
                self.assertIn('Average response time: 10.0 ms.', updated)
                self.assertIn('The file english.csv was exported.', updated)
                self.assertIn('The file english.statics.csv was exported.', updated)
                settings.setLanguage('es')
                services.journal.record(OperationEvent('wifi_disconnect', 'completed', {}))
                text = self.load_journal(journal, day)
                self.assertTrue(text.endswith('Se desconectó la interfaz Wi-Fi.\n'))

                tile = next(tile for tile in home.property('catalog').toVariant() if tile['id'] == 'journal')
                home.open.emit(tile['page'])
                app.app.processEvents()
                page = app.root.findChild(QObject, 'technicalJournalPage')
                self.assertTrue(page.isVisible())
                self.assertEqual(page.property('report'), text)
                settings.setTechnicalJournal(False)
                self.assertTrue(ping.start('192.0.2.99', 1, 1, 64))
                runner.handles[-1].finish()
                app.app.processEvents()
                self.assertEqual(journal.read(day), text)
                self.assertEqual(services.files.export('bitacora', day + '.txt', 'sda1'), day + '.txt')
                self.assertEqual((usb / (day + '.txt')).read_text(encoding='utf-8'), text)
                journal.deleteDay(day)
                self.wait_journal(journal)
                self.assertEqual(journal.days, [])
                self.assertEqual(activity.days, [day])
            finally:
                app.dispose()


if __name__ == '__main__':
    unittest.main()
