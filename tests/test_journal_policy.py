import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mulita.adapters.settings_store import JsonSettingsStore, MemorySettingsStore
from mulita.bootstrap import build_services
from mulita.config import AppConfig
from mulita.services.event_factory import make_event
from mulita.core.journal_tests import TEST_IDS
from mulita.core.models import WifiLink
from mulita.core.settings import Settings, settings_from_dict
from mulita.services.journal import TechnicalJournalService
from tests.fakes import FakeRunner


class JournalPolicyTest(unittest.TestCase):
    def test_each_test_can_be_disabled_without_affecting_others(self):
        for disabled in TEST_IDS:
            settings = SimpleNamespace(current=Settings(technical_journal=True,
                journal_tests=tuple(key for key in TEST_IDS if key != disabled)))
            render, append = Mock(return_value=['test']), Mock()
            journal = TechnicalJournalService(settings, render, append)
            for test in TEST_IDS:
                journal.record(make_event(test, 'started', {}))
            self.assertEqual(len(render.call_args_list), len(TEST_IDS) - 1)
            self.assertNotIn(disabled, [call.args[0].action for call in render.call_args_list])
            render.reset_mock()
            journal.record(make_event('export', 'completed', {'test': disabled}, 'test.csv'))
            journal.record(make_event('web_export', 'completed', {'test': disabled}, 'test.csv'))
            render.assert_not_called()

    def test_system_events_and_unclassified_exports_never_reach_renderer(self):
        render = Mock(return_value=['test'])
        journal = TechnicalJournalService(SimpleNamespace(current=Settings(technical_journal=True)), render, Mock())
        for action in ('update', 'restart', 'poweroff', 'wifi_connect', 'wifi_disconnect', 'ipv4_wifi',
                       'ipv4_ethernet', 'vlan', 'rename', 'copy', 'delete', 'export', 'web_export'):
            for phase in ('started', 'completed', 'failed'):
                journal.record(make_event(action, phase, {}, 'file.csv'))
        journal.record(make_event('export', 'completed', {'place': 'bitacora'}, 'journal.csv'))
        render.assert_not_called()

    def test_mixed_batch_only_records_enabled_diagnostics(self):
        render = Mock(return_value=['test'])
        journal = TechnicalJournalService(SimpleNamespace(current=Settings(technical_journal=True, journal_tests=('capture',))), render, Mock())
        journal.record(make_event('export_many', 'completed',
            {'items': [('ping', 'ping.csv'), ('captura', 'capture.pcap'), ('bitacora', 'journal.txt')]}, 3))
        self.assertEqual(render.call_count, 1)
        self.assertEqual(render.call_args.args[0].result.names, ('capture.pcap',))
        self.assertEqual(render.call_args.args[0].parameters.place, 'captura')

    def test_preferences_persist_and_missing_legacy_preferences_enable_all_tests(self):
        self.assertEqual(settings_from_dict({'technicalJournal': True}).journal_tests, TEST_IDS)
        self.assertEqual(settings_from_dict({'journalTests': []}).journal_tests, TEST_IDS)
        with tempfile.TemporaryDirectory() as folder:
            config = AppConfig(test_mode=True, capture_dir=Path(folder) / 'captures', settings_path=Path(folder) / 'settings.json')
            services = build_services(config, runner=FakeRunner())
            try:
                services.settings.set_journal_test('ping', False)
                services.settings.set_technical_journal(True)
                stored = JsonSettingsStore(config.settings_path).load()
                self.assertNotIn('ping', stored.journal_tests)
                self.assertIn('wifi_info', stored.journal_tests)
                services.settings.set_technical_journal(False)
                self.assertNotIn('ping', services.settings.current.journal_tests)
            finally:
                services.close_journals()

    def test_wifi_info_records_localized_results_and_obeys_its_switch(self):
        with tempfile.TemporaryDirectory() as folder:
            config = AppConfig(test_mode=True, capture_dir=Path(folder), settings_path=Path(folder) / 'settings.json')
            services = build_services(config, runner=FakeRunner(), settings_store=MemorySettingsStore(Settings(technical_journal=True)))
            try:
                with patch.object(services.wifi, 'interface', return_value='wlan0'), patch.object(services.wifi, '_link', return_value=WifiLink(interface='wlan0', ssid='Lab', address='192.0.2.1')):
                    services.wifi.status()
                    services.journals['bitacora'].flush()
                    path = next((Path(folder) / 'bitacora').glob('*.txt'))
                    text = path.read_text(encoding='utf-8')
                    self.assertIn('Se consultó la información Wi-Fi', text)
                    self.assertIn('192.0.2.1', text)
                    services.settings.set_journal_test('wifi_info', False)
                    services.wifi.status()
                    services.journals['bitacora'].flush()
                    self.assertEqual(path.read_text(encoding='utf-8'), text)
            finally:
                services.close_journals()
