import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from tests.qt_support import qt_app
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.nmapscan import NmapController


class Deferred:
    def __init__(self): self.jobs = []
    def background(self, task, success, failure): self.jobs.append((task, success, failure))
    def wrap(self, callback): return callback


class NmapControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = qt_app()

    def setUp(self):
        self.dispatcher = Deferred()
        self.service = SimpleNamespace(reset_cancel=Mock(), request_cancel=Mock(), stop=Mock(),
                                       discard=Mock(), launch=Mock(), is_running=False)
        self.controller = NmapController(BridgeContext(None, None, self.dispatcher, Notifier()), self.service)

    def test_history_completion_cannot_unlock_pending_preparation(self):
        c = self.controller
        c.openRun('old')
        self.assertTrue(c.start('{}'))
        self.dispatcher.jobs[0][1](({'status': 'ok', 'command': 'OLD'}, ()))
        self.assertEqual(c.phase, 'starting')
        self.assertEqual(c.command, '')
        self.assertFalse(c.start('{}'))
        self.assertEqual(len(self.dispatcher.jobs), 2)

    def test_latest_history_and_comparison_win(self):
        c = self.controller
        c.openRun('first'); c.openRun('second')
        self.dispatcher.jobs[1][1](({'command': 'SECOND'}, ()))
        self.dispatcher.jobs[0][1](({'command': 'FIRST'}, ()))
        self.assertEqual(c.command, 'SECOND')
        c.compareRuns('a', 'b'); c.compareRuns('a', 'c')
        self.dispatcher.jobs[3][1]({'result': 'new'})
        self.dispatcher.jobs[2][1]({'result': 'old'})
        self.assertIn('new', c.compareJson)

    def test_cancel_during_prepare_discards_result_then_allows_restart(self):
        c = self.controller
        c.start('{}'); c.stop()
        self.assertFalse(c.start('{}'))
        prepared = object()
        self.dispatcher.jobs[0][1](prepared)
        self.service.discard.assert_called_once_with(prepared)
        self.service.launch.assert_not_called()
        self.assertEqual(c.phase, 'cancelled')
        self.assertTrue(c.start('{}'))

    def test_preparation_failure_allows_retry(self):
        self.controller.start('{}')
        self.dispatcher.jobs[0][2](OSError('failed'))
        self.assertTrue(self.controller.start('{}'))
