import tempfile
import unittest
import csv
import io
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from mulita.adapters.export_bundle import export_bundle
from mulita.config import Binaries, AppConfig
from mulita.bootstrap import build_services
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError
from mulita.core.models import PingReply, PingSummary
from mulita.services.diagnostics import PingService
from tests.fakes import FakeRunner


class ExportBundleTest(unittest.TestCase):
    def test_composition_injects_exporter_that_controls_staging_and_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = AppConfig(test_mode=True, capture_dir=root / 'captures', settings_path=root / 'settings.json')
            Path(config.ping_dir).mkdir(parents=True)
            published = {}

            @contextmanager
            def custom_exporter(destinations):
                with tempfile.TemporaryDirectory(dir=root) as staging:
                    # Different names ensure the service really uses the paths
                    # supplied by its dependency, not the destination paths.
                    paths = (Path(staging) / 'table', Path(staging) / 'summary')
                    yield paths
                    published.update((destination.name, staged.read_text(encoding='utf-8'))
                                     for destination, staged in zip(destinations, paths))

            services = build_services(config, runner=FakeRunner(), exporter=custom_exporter)
            try:
                replies = (PingReply(1, '8.8.8.8', '117', '20.1', 'ok'),)
                summary = PingSummary(target='8.8.8.8', transmitted='1', received='1', loss='0%')
                self.assertEqual(services.ping.save(replies, summary, 'injected'), 'injected.csv')
                rows = list(csv.DictReader(io.StringIO(published['injected.csv'])))
                self.assertEqual(rows[0]['source'], '8.8.8.8')
                stats = list(csv.DictReader(io.StringIO(published['injected.statics.csv'])))
                self.assertEqual(stats[0]['transmitted'], '1')
                self.assertEqual(list(Path(config.ping_dir).iterdir()), [])
            finally:
                services.close_journals()

    def test_injected_publication_failure_is_not_reported_as_a_success(self):
        with tempfile.TemporaryDirectory() as directory:
            @contextmanager
            def failing_exporter(destinations):
                with tempfile.TemporaryDirectory(dir=directory) as staging:
                    yield tuple(Path(staging) / path.name for path in destinations)
                    raise OSError('publication failed')
            service = PingService(FakeRunner(), CommandFactory(Binaries()), Path(directory), exporter=failing_exporter)
            events = []
            service.set_event_sink(events.append)
            with self.assertRaises(CommandFailedError) as failure:
                service.save((PingReply(1, '8.8.8.8', '117', '20.1', 'ok'),), None, 'failed')
            self.assertEqual(failure.exception.code, 'savePingFailed')
            self.assertEqual([event.phase for event in events], ['started', 'failed'])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_ping_second_write_failure_allows_same_name_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            service = PingService(FakeRunner(), CommandFactory(Binaries()), Path(directory), exporter=export_bundle)
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
