import os
import unittest
from unittest.mock import patch, sentinel

from mulita.bootstrap import main
from mulita.config import AppConfig, load_config


class QtStartupTest(unittest.TestCase):
    def test_configuration_retains_simulation_and_keyboard_options(self):
        with patch('mulita.config._installation_paths', return_value={}), \
                patch.dict(os.environ, {'MULITA_TEST': '0'}):
            default = load_config()
            simulation = load_config(['--test', '--no-keyboard'])
        self.assertFalse(default.test_mode)
        self.assertTrue(default.virtual_keyboard)
        self.assertTrue(simulation.test_mode)
        self.assertFalse(simulation.virtual_keyboard)

    def test_entry_point_runs_qt_and_propagates_exit_status(self):
        config = AppConfig(test_mode=True)
        with patch('mulita.bootstrap.load_config', return_value=config) as configure, \
                patch('mulita.bootstrap.build_services', return_value=sentinel.services), \
                patch('mulita.ui.qt.app.QtApplication') as application:
            application.return_value.run.return_value = 7
            with self.assertRaises(SystemExit) as stopped:
                main(['--test'])
        configure.assert_called_once_with(['--test'])
        application.assert_called_once_with(config, sentinel.services)
        application.return_value.run.assert_called_once_with()
        self.assertEqual(stopped.exception.code, 7)
