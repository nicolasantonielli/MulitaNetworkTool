import ast
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import Mock, patch

from mulita.adapters.journals import FileJournalRepository
from mulita.core.events import OperationEvent, EventSource
from mulita.core.event_payloads import OperationParameters, PingReport, ExportReport, SwitchReport
from mulita.core.models import PingSummary
from mulita.core.errors import ValidationError
from mulita.services.event_factory import make_event
from mulita.services.operation_events import operation, session
from mulita.services.files import CaptureFilesService


class EventContractsTest(unittest.TestCase):
    def test_wrong_contracts_fail_before_reaching_a_renderer(self):
        with self.assertRaises(TypeError):
            OperationEvent('ping', 'started', {'target': '8.8.8.8'})
        with self.assertRaises(TypeError):
            OperationEvent('ping', 'completed', OperationParameters(), ExportReport(('test.csv',)))
        with self.assertRaises(TypeError):
            OperationEvent('ping', 'completed', OperationParameters(), PingReport({}, 1))
        with self.assertRaises(TypeError):
            OperationEvent('export', 'completed', OperationParameters(), ExportReport(['test.csv']))
        event = OperationEvent('ping', 'completed', OperationParameters(target='8.8.8.8'), PingReport(PingSummary(), 1))
        with self.assertRaises(FrozenInstanceError):
            event.result.replies = 10

    def test_service_mutation_cannot_change_a_published_result(self):
        report = {'interface': 'eth0', 'cancelled': False, 'frames': 1,
                  'neighbors': [{'name': 'Switch', 'port': 'Gi1'}]}
        event = make_event('switch', 'completed', {}, report)
        report['neighbors'][0]['port'] = 'changed'
        self.assertIsInstance(event.result, SwitchReport)
        self.assertEqual(event.result.neighbors[0].port, 'Gi1')
        private = make_event('capture', 'started', {'interface': 'eth0', 'password': 'secret'})
        self.assertNotIn('secret', repr(private))

    def test_invalid_result_does_not_change_diagnostic_return_value(self):
        class Service(EventSource):
            @operation('ping')
            def run(self):
                return {'unexpected': 'payload'}
        service = Service()
        sink = Mock()
        service.set_event_sink(sink)
        with self.assertLogs('mulita.services.event_factory', level='ERROR'):
            self.assertEqual(service.run(), {'unexpected': 'payload'})
        self.assertEqual(sink.call_count, 1)  # Start is valid; completion is rejected.

    def test_formatter_has_no_dictionary_payload_access(self):
        source = (Path(__file__).parents[1] / 'mulita/presentation/journal.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                self.assertNotIn(node.value.id, ('p', 'value', 'row'))

    def test_invalid_stream_result_does_not_suppress_completion_callback(self):
        class Service(EventSource):
            findings = {'unexpected': 'payload'}

            @session('tls', 'target')
            def run(self, target, on_output=None, on_exit=None):
                self.finished = on_exit
        service = Service()
        sink, completed = Mock(), Mock()
        service.set_event_sink(sink)
        service.run('example.org', on_exit=completed)
        with self.assertLogs('mulita.services.event_factory', level='ERROR'):
            service.finished(0)
        completed.assert_called_once_with(0)
        self.assertEqual(sink.call_count, 1)


class JournalFilesContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'bitacora'
        self.folder.mkdir()
        self.repo = FileJournalRepository(self.folder, '.txt')
        self.service = CaptureFilesService(self.root, journal_files={'bitacora': self.repo})
        (self.folder / '2026-11-05.txt').write_text('report')
        (self.folder / '2026-11-05.jsonl').write_text('metadata')

    def test_report_moves_and_deletes_as_a_complete_unit(self):
        self.service.copy('bitacora', '2026-11-05.txt', 'copy')
        self.service.rename('bitacora', 'copy.txt', 'renamed')
        self.assertEqual((self.folder / 'renamed.jsonl').read_text(), 'metadata')
        self.assertFalse((self.folder / 'copy.jsonl').exists())
        self.service.delete_many([('bitacora', 'renamed.txt'), ('bitacora', '2026-11-05.txt')])
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_collisions_and_failed_copy_preserve_original_report(self):
        (self.folder / 'occupied.jsonl').write_text('existing')
        with self.assertRaises(ValidationError):
            self.service.rename('bitacora', '2026-11-05.txt', 'occupied')
        import shutil
        original = shutil.copyfile
        def fail_metadata(src, dst):
            if src.suffix == '.jsonl':
                raise OSError('disk full')
            return original(src, dst)
        with patch('mulita.adapters.journals.shutil.copyfile', side_effect=fail_metadata):
            with self.assertRaises(OSError):
                self.service.copy('bitacora', '2026-11-05.txt', 'partial')
        self.assertFalse((self.folder / 'partial.txt').exists())
        self.assertEqual((self.folder / '2026-11-05.txt').read_text(), 'report')
        self.assertEqual((self.folder / '2026-11-05.jsonl').read_text(), 'metadata')

    def test_file_service_uses_contract_without_knowing_storage_layout(self):
        manager = Mock()
        service = CaptureFilesService(self.root, journal_files={'bitacora': manager})
        service.rename('bitacora', 'source', 'target')
        service.copy('bitacora', 'source', 'target')
        service.delete('bitacora', 'source')
        manager.rename_file.assert_called_once_with('source.txt', 'target.txt')
        manager.copy_file.assert_called_once_with('source.txt', 'target.txt')
        manager.delete_file.assert_called_once_with('source.txt')
        source = (Path(__file__).parents[1] / 'mulita/services/files.py').read_text(encoding='utf-8')
        self.assertNotIn('.jsonl', source)
        with self.assertRaises(ValidationError):
            CaptureFilesService(self.root).delete('bitacora', '2026-11-05.txt')

    def test_invalid_companion_does_not_delete_primary_and_missing_rename_fails(self):
        (self.folder / 'broken.txt').write_text('keep')
        (self.folder / 'broken.jsonl').mkdir()
        with self.assertRaises(ValidationError):
            self.service.delete('bitacora', 'broken.txt')
        self.assertEqual((self.folder / 'broken.txt').read_text(), 'keep')
        with self.assertRaises(ValidationError):
            self.service.rename('bitacora', 'missing.txt', 'missing.txt')
