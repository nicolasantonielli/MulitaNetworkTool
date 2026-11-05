"""Slow storage must not stall Qt or replace a newer journal selection."""
import ast
from datetime import datetime
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from tests.qt_support import qt_app
from PyQt5.QtCore import QTimer
from PyQt5.QtTest import QTest
from mulita.adapters.journals import FileJournalRepository
from mulita.adapters.settings_store import MemorySettingsStore
from mulita.bootstrap import build_services
from mulita.config import AppConfig
from mulita.services.event_factory import make_event
from mulita.core.platform import UsbDrive
from mulita.core.journals import JournalSnapshot
from mulita.core.settings import Settings
from mulita.services.journal_archive import JournalArchive
from mulita.ui.qt.bridge.activity import DailyJournal, ActivityController
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.dispatcher import QtDispatcher
from tests.fakes import FakeRunner, FakeStorage


class SlowRepository:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = []
        self.slow_read = True
        self.slow_write = False
        self.fail_delete = False
        self.texts = {'2026-11-05': 'new', '2026-11-04': 'old'}

    def snapshot(self, day, known_day='', known_revision=''):
        self.calls.append(('read', day, threading.get_ident()))
        if self.slow_read:
            self.entered.set()
            self.release.wait(3)
        days = tuple(sorted(self.texts, reverse=True))
        selected = day if day in days else (days[0] if days else '')
        text = self.texts.get(selected, '')
        return JournalSnapshot(days, selected, text, text)

    def append(self, now, line):
        self.calls.append(('write', line, threading.get_ident()))
        if self.slow_write:
            self.entered.set()
            self.release.wait(3)

    def delete(self, day):
        self.calls.append(('delete', day, threading.get_ident()))
        if self.fail_delete:
            raise PermissionError('read-only test journal')
        self.texts.pop(day, None)


class JournalArchiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        self.repository = SlowRepository()
        self.archive = JournalArchive(self.repository)
        self.dispatcher = QtDispatcher()
        self.notifier = Notifier()
        settings = SimpleNamespace(current=Settings(activity_logging=True), subscribe=lambda _: None)
        self.ctx = BridgeContext(None, settings, self.dispatcher, self.notifier)
        self.controller = DailyJournal(self.ctx, self.archive)

    def tearDown(self):
        self.repository.release.set()
        self.controller.close()
        self.archive.close()
        self.dispatcher.shutdown()
        self.app.processEvents()

    def settle(self):
        for _ in range(200):
            QTest.qWait(10)
            if not self.controller.busy:
                return
        self.fail('Journal remained busy')

    def test_slow_read_keeps_gui_responsive_and_properties_use_only_memory(self):
        ticks = []
        timer = QTimer()
        timer.timeout.connect(lambda: ticks.append(True))
        timer.start(5)
        start = time.monotonic()
        self.controller.refresh('2026-11-05')
        self.assertLess(time.monotonic() - start, .5)
        self.assertTrue(self.repository.entered.wait(1))
        for _ in range(10):
            self.assertEqual(self.controller.days, [])
            self.assertEqual(self.controller.read('2026-11-05'), '')
            self.assertEqual(self.controller.revision('2026-11-05'), '')
        QTest.qWait(60)
        timer.stop()
        self.assertGreater(len(ticks), 1)
        self.assertTrue(self.controller.busy)
        self.assertEqual(len(self.repository.calls), 1)
        self.assertNotEqual(self.repository.calls[0][2], threading.get_ident())
        self.repository.release.set()
        self.settle()
        self.assertEqual(self.controller.report, 'new')

    def test_late_read_does_not_replace_new_selection_and_polls_are_coalesced(self):
        seen = []
        self.controller.changed.connect(lambda: seen.append(self.controller.day))
        self.controller.refresh('2026-11-04')
        self.assertTrue(self.repository.entered.wait(1))
        for _ in range(20):
            self.controller.refresh('2026-11-05')
        self.repository.release.set()
        self.settle()
        self.assertEqual(seen, ['2026-11-05'])
        self.assertEqual(len(self.repository.calls), 2)
        self.assertEqual(self.controller.report, 'new')

    def test_delete_invalidates_pending_read_and_updates_selection(self):
        seen = []
        self.controller.changed.connect(lambda: seen.append(self.controller.day))
        self.controller.refresh('2026-11-05')
        self.assertTrue(self.repository.entered.wait(1))
        self.controller.deleteDay('2026-11-05')
        self.repository.release.set()
        self.settle()
        self.assertEqual(seen, ['2026-11-04'])
        self.assertEqual(self.controller.days, ['2026-11-04'])
        self.assertEqual([call[0] for call in self.repository.calls], ['read', 'delete', 'read'])

    def test_failed_delete_reports_once_and_keeps_existing_text(self):
        self.repository.slow_read = False
        self.controller.refresh('2026-11-05')
        self.settle()
        self.repository.fail_delete = True
        errors = []
        self.notifier.notified.connect(lambda *args: errors.append(args))
        with self.assertLogs('mulita.services.journal_archive', level='ERROR'):
            self.controller.deleteDay('2026-11-05')
            self.settle()
        self.assertEqual(self.controller.report, 'new')
        self.assertEqual(len(errors), 1)
        self.assertFalse(self.controller.busy)

    def test_activity_write_is_off_thread_and_close_drains_pending_writes(self):
        activity = ActivityController(self.ctx, self.archive)
        self.repository.slow_write = True
        start = time.monotonic()
        activity.record('pingTitle', '8.8.8.8', 'activityStarted')
        self.assertLess(time.monotonic() - start, .5)
        self.assertTrue(self.repository.entered.wait(1))
        closed = threading.Event()
        thread = threading.Thread(target=lambda: (self.archive.close(), closed.set()))
        thread.start()
        self.assertFalse(closed.wait(.05))
        self.repository.release.set()
        thread.join(2)
        self.assertTrue(closed.is_set())
        self.assertNotEqual(self.repository.calls[0][2], threading.get_ident())
        activity.close()

    def test_closed_controller_ignores_late_result(self):
        seen = []
        self.controller.changed.connect(lambda: seen.append(True))
        self.controller.refresh('2026-11-05')
        self.assertTrue(self.repository.entered.wait(1))
        self.controller.close()
        self.repository.release.set()
        self.archive.flush()
        QTest.qWait(30)
        self.assertEqual(seen, [])

    def test_qt_journal_controller_has_no_filesystem_dependency(self):
        path = Path(__file__).resolve().parents[1] / 'mulita/ui/qt/bridge/activity.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertFalse(node.module.startswith(('pathlib', 'mulita.adapters', 'mulita.servers')))
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, ('read_text', 'write_text', 'unlink', 'stat', 'glob', 'open'))


class FileJournalRepositoryTest(unittest.TestCase):
    def test_export_waits_for_queued_writes_and_final_action_drains_its_own_events(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = AppConfig(test_mode=True, capture_dir=root / 'captures', settings_path=root / 'settings.json')
            services = build_services(config, runner=FakeRunner(),
                settings_store=MemorySettingsStore(Settings(technical_journal=True)))
            archive = services.journals['bitacora']
            entered, release = threading.Event(), threading.Event()
            original = archive._repository.append
            def slow_append(now, line):
                entered.set()
                release.wait(3)
                original(now, line)
            usb = root / 'usb'
            usb.mkdir()
            services.files._storage = FakeStorage((UsbDrive('sda1', 'USB', str(usb)),))
            try:
                with patch.object(archive._repository, 'append', side_effect=slow_append):
                    event = make_event('ping', 'started', {'target': '8.8.8.8'})
                    services.journal.record(event)
                    self.assertTrue(entered.wait(1))
                    day = event.occurred_at.date().isoformat()
                    with ThreadPoolExecutor(max_workers=1) as worker:
                        exported = worker.submit(services.files.export, 'bitacora', day + '.txt', 'sda1')
                        self.assertFalse(exported.done())
                        release.set()
                        self.assertEqual(exported.result(timeout=3), day + '.txt')
                    self.assertIn('Se hizo ping', (usb / (day + '.txt')).read_text(encoding='utf-8'))
                # Read the file directly after completion, without an extra flush.
                # The restart callback must be safe to replace the process now.
                with patch.dict('os.environ', {'INVOCATION_ID': ''}):
                    self.assertIsNone(services.maintenance.run_final_action(services.maintenance.reset))
                text = (config.capture_dir / 'bitacora' / (day + '.txt')).read_text(encoding='utf-8')
                self.assertEqual(text, (usb / (day + '.txt')).read_text(encoding='utf-8'))
            finally:
                release.set()
                services.close_journals()

    def test_cached_revision_external_changes_and_deleted_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repo = FileJournalRepository(root, '.txt')
            now = datetime(2026, 11, 5, 12, 30)
            repo.append(now, 'First entry')
            first = repo.snapshot('')
            self.assertEqual(first.text, 'First entry\n')
            self.assertIsNone(repo.snapshot(first.day, first.day, first.revision).text)
            (root / '2026-11-05.txt').write_text('Updated from web', encoding='utf-8')
            updated = repo.snapshot(first.day, first.day, first.revision)
            self.assertEqual(updated.text, 'Updated from web')
            (root / '2026-11-04.txt').write_text('Previous day', encoding='utf-8')
            repo.delete('2026-11-05')
            self.assertEqual(repo.snapshot(first.day).day, '2026-11-04')
            with self.assertRaises(ValueError):
                repo.delete('../outside')
            self.assertEqual(repo.snapshot('').text, 'Previous day')
