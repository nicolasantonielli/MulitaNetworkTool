import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from mulita.config import AppConfig, load_config, PROJECT_ROOT, Binaries
from mulita.core.storage import PLACES
from mulita.core.commands import CommandFactory
from scripts.configure_installation import installation_config, unit_text, write_atomic


class InstallationPathsTest(unittest.TestCase):
    def test_direct_configuration_and_replacement_derive_all_storage_paths(self):
        initial = AppConfig(capture_dir=self.root / 'first')
        updated = replace(initial, capture_dir=self.root / 'second')
        for config in (initial, updated):
            for field, place in [('trace_dir', 'traza'), ('ping_dir', 'ping'),
                                 ('wifi_dir', 'wifi'), ('scan_dir', 'escaneo'),
                                 ('nmap_dir', 'nmap'), ('tls_dir', 'tls'),
                                 ('discovery_dir', 'descubrimiento'),
                                 ('servers_dir', 'servidores'), ('public_ip_dir', 'publica')]:
                self.assertEqual(getattr(config, field), config.storage.folder(place))
                self.assertEqual(getattr(config, field).parent, config.capture_dir)
            for place in PLACES:
                self.assertEqual(config.storage.folder(place.id), config.capture_dir / place.folder)

    def test_file_browser_and_nmap_share_custom_location_and_identifier(self):
        from tests.fakes import FakeRunner
        from mulita.services.files import CaptureFilesService
        from mulita.services.nmapscan import NmapScanService
        config = AppConfig(capture_dir=self.root / 'custom')
        config.wifi_dir.mkdir(parents=True)
        path = config.wifi_dir / 'link.csv'
        path.write_text('ssid,Office', encoding='utf-8')
        browser = CaptureFilesService(config.capture_dir)
        scanner = NmapScanService(FakeRunner(), CommandFactory(Binaries()),
                                  config.nmap_dir, self.root / 'state', config.capture_dir)
        self.assertEqual(browser.list_files()[0].place, 'wifi')
        self.assertEqual(scanner.list_files()[0]['token'], '@wifi/link.csv')
        self.assertEqual(scanner.resolve('@wifi/link.csv'), str(path.resolve()))

    def test_server_program_path_is_injected(self):
        directory = self.root / 'deployment with spaces'
        command = CommandFactory(Binaries(), directory).ntp_server(123, 2)
        self.assertEqual(command[2], str(directory / 'ntp.py'))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'user home'
        self.repo = self.root / 'repository with spaces'
        self.path = self.root / 'config.json'

    def load(self, data):
        self.path.write_text(json.dumps(data), encoding='utf-8')
        with patch.dict(os.environ, {'MULITA_CONFIG': str(self.path)}):
            return load_config()

    def test_installed_user_paths_ignore_service_home(self):
        data = installation_config(self.repo, 'nico', self.home, {})
        with patch('mulita.config.Path.home', return_value=self.root / 'root-user'):
            config = self.load(data)
        self.assertEqual(config.capture_dir, self.home / 'capturas')
        self.assertEqual(config.settings_path, self.home / '.config/mulita/settings.json')
        self.assertEqual(config.servers_state_dir, self.home / '.config/mulita/servers')
        self.assertEqual(config.wifi_dir, config.capture_dir / 'wifi')
        self.assertEqual(config.repository_dir, str(PROJECT_ROOT))
        self.assertEqual(config.installation_user, 'nico')

    def test_custom_captures_propagate_to_all_tools(self):
        capture = self.root / 'data'
        state = self.root / 'private'
        config = self.load(installation_config(self.repo, 'nico', self.home, {}, capture, state))
        for field, child in [('trace_dir', 'trazas'), ('ping_dir', 'ping'), ('wifi_dir', 'wifi'),
                             ('scan_dir', 'escaneo'), ('nmap_dir', 'nmap'), ('tls_dir', 'tls'),
                             ('discovery_dir', 'descubrimiento'), ('servers_dir', 'servidores'),
                             ('public_ip_dir', 'internet')]:
            self.assertEqual(getattr(config, field), capture / child)
        self.assertEqual(config.settings_path, state / 'settings.json')

    def test_reinstallation_preserves_existing_data_paths(self):
        capture, state = self.root / 'old data', self.root / 'old state'
        previous = {'capture_dir': str(capture), 'state_dir': str(state)}
        data = installation_config(self.repo, 'nico', self.home, previous)
        self.assertEqual(data['capture_dir'], str(capture))
        self.assertEqual(data['state_dir'], str(state))

    def test_legacy_data_is_retained_and_can_be_overridden(self):
        legacy = self.root / 'legacy-root'
        (legacy / 'capturas').mkdir(parents=True)
        (legacy / '.config/mulita').mkdir(parents=True)
        data = installation_config(self.repo, 'nico', self.home, {}, legacy_home=legacy)
        self.assertEqual(data['capture_dir'], str(legacy / 'capturas'))
        self.assertEqual(data['state_dir'], str(legacy / '.config/mulita'))
        data = installation_config(self.repo, 'nico', self.home, {},
                                   self.root / 'new data', self.root / 'new state', legacy)
        self.assertEqual(data['capture_dir'], str(self.root / 'new data'))

    def test_invalid_config_does_not_fall_back_to_another_directory(self):
        for data in ([], {'capture_dir': 'relative'}, {'state_dir': None}):
            with self.assertRaises(ValueError):
                self.load(data)

    def test_no_configuration_uses_current_home(self):
        with patch.dict(os.environ, {'MULITA_CONFIG': str(self.path)}):
            with self.assertRaises(ValueError):
                load_config()
        self.path.write_text('{}', encoding='utf-8')
        with patch.dict(os.environ, {'MULITA_CONFIG': str(self.path)}), \
                patch('mulita.config.Path.home', return_value=self.home):
            config = load_config()
        self.assertEqual(config.capture_dir, self.home / 'capturas')

    def test_private_state_cannot_be_inside_shared_captures(self):
        with self.assertRaises(ValueError):
            installation_config(self.repo, 'nico', self.home, {},
                                self.root / 'captures', self.root / 'captures/private')

    def test_systemd_directory_is_unquoted_while_exec_and_environment_are_quoted(self):
        repo = PurePosixPath('/home/nico/repository with spaces/100% $folder')
        home = PurePosixPath('/home/nico')
        text = unit_text(repo, home, PurePosixPath('/etc/mulita/config.json'))
        self.assertIn('WorkingDirectory=/home/nico/repository with spaces/100%% $folder\n', text)
        self.assertNotIn('WorkingDirectory="', text)
        self.assertIn('100%% $$folder', text)
        self.assertIn('Environment="HOME=' + str(home) + '"', text)
        self.assertIn('Environment="MULITA_CONFIG=', text)

    def test_working_directory_regression_for_reported_installation(self):
        text = unit_text(PurePosixPath('/home/nico/MulitaNetworkTool'),
                         PurePosixPath('/home/nico'), PurePosixPath('/etc/mulita/config.json'))
        line = next(line for line in text.splitlines() if line.startswith('WorkingDirectory='))
        self.assertEqual(line, 'WorkingDirectory=/home/nico/MulitaNetworkTool')
        self.assertIn('ExecStart="/home/nico/MulitaNetworkTool/.venv/bin/python" main.py', text)

    def test_atomic_config_write(self):
        write_atomic(self.path, '{"user": "nico"}\n')
        self.assertEqual(json.loads(self.path.read_text())['user'], 'nico')
        self.assertEqual(list(self.root.glob('.mulita-*')), [])

    def test_update_can_run_as_repository_owner(self):
        command = CommandFactory(Binaries()).update(str(self.repo), 'origin', 'v3.1', 'nico')
        self.assertEqual(command[:4], ['/usr/sbin/runuser', '-u', 'nico', '--'])
        self.assertEqual(command[4:], ['/usr/bin/git', '-C', str(self.repo), 'pull', 'origin', 'v3.1'])
