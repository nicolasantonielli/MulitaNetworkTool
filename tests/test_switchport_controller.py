import json
import tempfile
import unittest
from pathlib import Path

from tests.qt_support import qt_app
from tests.fakes import FakeRunner

from mulita.adapters.settings_store import MemorySettingsStore
from mulita.bootstrap import build_services
from mulita.config import AppConfig
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.switchport import SwitchPortController


class Deferred:
    def wrap(self, callback):
        return callback

    def background(self, task, success, failure):
        self.task, self.success, self.failure = task, success, failure

    def finish(self):
        try:
            result = self.task()
        except Exception as error:
            self.failure(error)
        else:
            self.success(result)


class SwitchPortControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        config = AppConfig(test_mode=True, capture_dir=Path(temp.name))
        self.services = build_services(config, runner=FakeRunner(), settings_store=MemorySettingsStore())
        self.dispatcher = Deferred()
        self.ctx = BridgeContext(config, self.services, self.dispatcher, Notifier())
        self.controller = SwitchPortController(self.ctx)

    def test_demo_is_marked_and_save_produces_a_report(self):
        self.controller.start('eth0', 60)
        self.assertTrue(self.controller.running)
        self.dispatcher.finish()
        self.assertFalse(self.controller.running)
        self.assertTrue(json.loads(self.controller.reportJson)['simulated'])
        self.controller.save()
        self.assertEqual(len(list(self.services.switchport.directory.glob('*.json'))), 1)

    def test_cancel_before_worker_starts_is_preserved_and_restart_is_blocked(self):
        self.controller.start('eth0', 60)
        original = self.dispatcher.task
        self.controller.stop()
        self.controller.start('eth1', 60)
        self.assertIs(self.dispatcher.task, original)
        self.assertTrue(self.controller.running)
        self.dispatcher.finish()
        report = json.loads(self.controller.reportJson)
        self.assertTrue(report['cancelled'])
        self.assertEqual(report['interface'], 'eth0')
        self.assertFalse(self.controller.running)

    def test_shutdown_cancels_pending_capture(self):
        self.controller.start('eth0', 60)
        self.services.shutdown()
        self.dispatcher.finish()
        self.assertTrue(json.loads(self.controller.reportJson)['cancelled'])
