import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mulita.adapters.export_bundle import export_bundle
from mulita.config import Binaries
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError
from mulita.core.models import PingReply
from mulita.services.diagnostics import PingService
from tests.fakes import FakeRunner


class ExportBundleTest(unittest.TestCase):
    def test_ping_second_write_failure_allows_same_name_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            service = PingService(FakeRunner(), CommandFactory(Binaries()), Path(directory))
            replies = (PingReply(1, '8.8.8.8', '117', '20.1', 'ok'),)
            with patch('mulita.services.diagnostics._write_statics', side_effect=OSError('full')):
                with self.assertRaises(CommandFailedError):
                    service.save(replies, None, 'retry')
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertEqual(service.save(replies, None, 'retry'), 'retry.csv')
            self.assertEqual(len(list(Path(directory).iterdir())), 2)

    def test_publish_failure_removes_only_our_files(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'first', Path(directory) / 'second'
            second.write_text('existing')
            with self.assertRaises(FileExistsError):
                with export_bundle((first, second)) as staged:
                    for path in staged:
                        path.write_text('new')
            self.assertFalse(first.exists())
            self.assertEqual(second.read_text(), 'existing')

    def test_copy_failure_rolls_back_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = (Path(directory) / 'first', Path(directory) / 'second')
            with patch('mulita.adapters.export_bundle.shutil.copyfileobj', side_effect=OSError('full')):
                with self.assertRaises(OSError):
                    with export_bundle(paths) as staged:
                        for path in staged:
                            path.write_text('new')
            self.assertEqual(list(Path(directory).iterdir()), [])
