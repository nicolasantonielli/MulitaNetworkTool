import csv
import io
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from mulita.adapters.journals import FileJournalRepository
from mulita.services.event_factory import make_event
from mulita.core.errors import ValidationError
from mulita.core.journal_entries import journal_csv
from mulita.core.models import PingSummary, TraceHop, PortFinding, SpeedTestResult, WifiLink
from mulita.presentation.journal_results import display_results
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
        event = make_event('ping', 'started', {'target': '8.8.8.8'}, occurred_at=self.now)
        self.repo.append(self.now, render_record(event, language))
        summary = PingSummary(target='8.8.8.8', transmitted='2', received='1', loss='50%', average='10')
        completed = make_event('ping', 'completed', {'target': '8.8.8.8'}, {'summary': summary, 'replies': 1}, event.operation_id, self.now)
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
        self.assertEqual(len(rows), 2)  # Multiline results remain inside one CSV cell.
        self.assertEqual(len(rows[1]), 4)
        self.assertIn('\nEnviados: 2\nRecibidos: 1\nPérdida: 50%', rows[1][3])
        snapshot = self.repo.snapshot(self.day)
        self.assertEqual(snapshot.entries, entries)
        self.assertIsNone(self.repo.snapshot(self.day, self.day, snapshot.revision).entries)

    def test_diagnostic_results_have_separate_rows_in_both_languages(self):
        cases = [
            ('trace', (TraceHop(1, '192.0.2.1', '0%', '1', '10', '10', '10', '10', '0'),
                       TraceHop(2, '192.0.2.2', '0%', '1', '20', '20', '20', '20', '0')), ('192.0.2.1', '192.0.2.2')),
            ('ports', (PortFinding('192.0.2.1', '80', 'tcp', 'open', 'http'),
                       PortFinding('192.0.2.1', '443', 'tcp', 'open', 'https')), ('80/tcp', '443/tcp')),
            ('speed', SpeedTestResult(10000000, 2000000), ('10.00 Mbps', '2.00 Mbps')),
            ('wifi_info', WifiLink(interface='wlan0', ssid='Lab', address='192.0.2.1'), ('Lab', 'wlan0', '192.0.2.1')),
        ]
        for language in ('es', 'en'):
            for action, value, expected in cases:
                record = render_record(make_event(action, 'completed', {'target': '192.0.2.1'}, value), language)
                lines = record.results.splitlines()
                indices = [next(index for index, line in enumerate(lines) if text in line) for text in expected]
                self.assertEqual(len(set(indices)), len(expected))

    def test_old_prose_gets_visual_breaks_without_breaking_addresses(self):
        old = 'Resultado del ping a 2001:db8::1: se enviaron 2 paquetes. Tiempo medio de respuesta: 1.5 ms.'
        displayed = display_results(old)
        self.assertIn('2001:db8::1:\n', displayed)
        self.assertIn('\nTiempo medio', displayed)
        self.assertIn('1.5 ms.', displayed)
        self.assertEqual(display_results(displayed), displayed)

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
                                      journal_access=lambda _: self.repo.transaction(), journal_csv=self.repo.csv_bytes, journal_files={'bitacora': self.repo})
        service.set_event_sink(events.append)
        name = service.export_journal_csv(self.day, 'sda1')
        self.assertEqual(name, self.day + '.csv')
        self.assertEqual((usb / name).read_bytes(), self.repo.csv_bytes(self.day))
        self.assertEqual(events[-1].result.names, (name,))
        with self.assertRaises(ValidationError):
            service.export_journal_csv(self.day, 'sda1')
        service.copy('bitacora', self.day + '.txt', '2026-11-06.txt')
        self.assertEqual(self.repo.read_entries('2026-11-06'), self.repo.read_entries(self.day))
        service.delete('bitacora', '2026-11-06.txt')
        self.assertFalse((self.root / 'bitacora' / '2026-11-06.jsonl').exists())
