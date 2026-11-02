import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from tests.qt_support import qt_app
from PyQt5.QtCore import QTimer
from mulita.core.models import WifiLink
from mulita.ui.qt.bridge.base import BridgeContext, Notifier, Controller
from mulita.ui.qt.bridge.wifi import WifiController
from mulita.ui.qt.bridge.switchport import SwitchPortController
from mulita.ui.qt.bridge.tools import _picked
from mulita.ui.qt.dispatcher import QtDispatcher


class Deferred:
    calls = 0
    def background(self, task, success, failure):
        self.calls += 1
        self.task, self.success, self.failure = task, success, failure


class ExportTasksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def pump(self, condition):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition(): return
            time.sleep(.005)
        self.fail('timeout')

    def test_slow_wifi_save_keeps_ui_responsive_and_rejects_duplicates(self):
        entered, release = threading.Event(), threading.Event()
        received = []
        def save(link):
            received.append(link)
            entered.set()
            release.wait(3)
            return 'wifi.csv'
        settings = SimpleNamespace(subscribe=lambda _: None,
                                   current=SimpleNamespace(language=SimpleNamespace(value='es')))
        ctx = BridgeContext(None, SimpleNamespace(wifi=SimpleNamespace(save=save), settings=settings),
                            QtDispatcher(), Notifier())
        controller = WifiController(ctx)
        controller._link = WifiLink(ssid='before')
        notifications, ticks = [], []
        ctx.notifier.notified.connect(lambda *args: notifications.append(args))
        try:
            controller.saveLink()
            self.assertTrue(entered.wait(1))
            controller._link = WifiLink(ssid='after')
            controller.saveLink()
            QTimer.singleShot(0, lambda: ticks.append(True))
            self.pump(lambda: ticks)
            self.assertTrue(controller.busy)
            self.assertEqual(notifications, [])
            self.assertEqual([x.ssid for x in received], ['before'])
        finally:
            release.set()
            self.pump(lambda: not controller.busy)
        self.assertEqual(notifications[0][0], 'success')

    def test_switch_save_uses_independent_nested_snapshot(self):
        dispatcher = Deferred()
        received = []
        service = SimpleNamespace(cancelled=threading.Event(),
                                  save=lambda report: received.append(report) or Path('saved.json'))
        controller = SwitchPortController(BridgeContext(
            None, SimpleNamespace(switchport=service), dispatcher, Notifier()))
        controller._report = {'neighbors': [{'name': 'before'}]}
        controller.save()
        controller._report['neighbors'][0]['name'] = 'after'
        controller.save()
        self.assertEqual(dispatcher.calls, 1)
        dispatcher.success(dispatcher.task())
        self.assertEqual(received, [{'neighbors': [{'name': 'before'}]}])
        self.assertFalse(controller.saving)

    def test_export_failure_unlocks_retry_and_notifies(self):
        dispatcher, notifier = Deferred(), Notifier()
        controller = Controller(BridgeContext(None, SimpleNamespace(), dispatcher, notifier))
        notifications = []
        notifier.notified.connect(lambda *args: notifications.append(args))
        controller._export(lambda: None, lambda _: self.fail('unexpected success'))
        dispatcher.failure(OSError('disk full'))
        self.assertFalse(controller.saving)
        self.assertEqual(notifications[0][0], 'error')
        controller._export(lambda: None, lambda _: None)
        self.assertEqual(dispatcher.calls, 2)

    def test_batch_export_preserves_file_identifiers(self):
        self.assertEqual(_picked('[{"place":"wifi","name":"Office.csv"}]'), [('wifi', 'Office.csv')])
