import csv
import io
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from mulita.adapters.journals import FileJournalRepository
from mulita.core.events import OperationEvent
from mulita.core.errors import ValidationError
from mulita.core.journal_entries import journal_csv
from mulita.core.models import PingSummary
from mulita.core.platform import UsbDrive
from mulita.core.settings import Settings, Theme, Language
from mulita.presentation.journal import render_record
from mulita.presentation.journal_web import timeline
from mulita.services.files import CaptureFilesService
from tests.fakes import FakeStorage


class TimelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = FileJournalRepository(self.root / 'bitacora', '.txt')
        self.now = datetime.fromisoformat('2026-11-05T12:55:01-03:00')
        self.day = '2026-11-05'

    def ping(self, language='es'):
        event = OperationEvent('ping', 'started', {'target': '8.8.8.8'}, occurred_at=self.now)
        self.repo.append(self.now, render_record(event, language))
        summary = PingSummary(target='8.8.8.8', transmitted='2', received='1', loss='50%', average='10')
        completed = replace(event, phase='completed', result={'summary': summary, 'replies': 1})
        self.repo.append(self.now, render_record(completed, language))

    def test_one_card_per_operation_and_csv_columns(self):
        self.ping()
        entries = self.repo.read_entries(self.day)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['time'], '12:55:01')
        rows = list(csv.reader(io.StringIO(self.repo.csv_bytes(self.day).decode('utf-8-sig'))))
        self.assertEqual(rows[0], ['fecha', 'tipo de prueba', 'texto', 'resultados'])
        self.assertEqual(rows[1][:3], ['2026-11-05T12:55:01-03:00', 'Ping', 'Se hizo ping a 8.8.8.8.'])
        self.assertIn('50%', rows[1][3])
        snapshot = self.repo.snapshot(self.day)
        self.assertEqual(snapshot.entries, entries)
        self.assertIsNone(self.repo.snapshot(self.day, self.day, snapshot.revision).entries)

    def test_legacy_and_damaged_metadata_preserve_history(self):
        self.ping()
        self.repo.append(self.now, '2026-05-11 12:57 - Nota anterior')
        metadata = self.root / 'bitacora' / (self.day + '.jsonl')
        with metadata.open('a', encoding='utf-8') as stream:
            stream.write('{broken\n')
        entries = self.repo.read_entries(self.day)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]['text'], 'Nota anterior')
        self.assertEqual(entries[0]['results'], '')
        # External replacement must not resurrect stale structured results.
        (self.root / 'bitacora' / (self.day + '.txt')).write_text('Replacement', encoding='utf-8')
        self.assertEqual(self.repo.read_entries(self.day)[0]['text'], 'Replacement')
        self.repo.delete(self.day)
        self.assertFalse(metadata.exists())
        self.assertEqual(self.repo.snapshot('').entries, ())

    def test_language_theme_and_untrusted_text(self):
        self.ping('en')
        entries = self.repo.read_entries(self.day)
        entry = dict(entries[0], text='<script>alert(1)</script>', results='=1+1, "quoted"\nsecond line')
        for theme, background in ((Theme.OSCURO, '#0E1319'), (Theme.CLARO, '#EEF2F6')):
            page = timeline([entry], Settings(theme=theme, language=Language.EN))
            self.assertIn(background, page)
            self.assertIn('Results', page)
            self.assertNotIn('<script>alert', page)
            self.assertIn('&lt;script&gt;', page)
        rows = list(csv.reader(io.StringIO(journal_csv([entry]).decode('utf-8-sig'))))
        self.assertEqual(rows[1][3], "'=1+1, \"quoted\"\nsecond line")

    def test_usb_csv_records_actual_name_and_protects_existing_files(self):
        self.ping()
        usb = self.root / 'usb'
        usb.mkdir()
        events = []
        service = CaptureFilesService(self.root, storage=FakeStorage((UsbDrive('sda1', 'USB', str(usb)),)),
                                      journal_access=lambda _: self.repo.transaction(), journal_csv=self.repo.csv_bytes)
        service.set_event_sink(events.append)
        name = service.export_journal_csv(self.day, 'sda1')
        self.assertEqual(name, self.day + '.csv')
        self.assertEqual((usb / name).read_bytes(), self.repo.csv_bytes(self.day))
        self.assertEqual(events[-1].result, name)
        with self.assertRaises(ValidationError):
            service.export_journal_csv(self.day, 'sda1')
        service.copy('bitacora', self.day + '.txt', '2026-11-06.txt')
        self.assertEqual(self.repo.read_entries('2026-11-06'), self.repo.read_entries(self.day))
        service.delete('bitacora', '2026-11-06.txt')
        self.assertFalse((self.root / 'bitacora' / '2026-11-06.jsonl').exists())
