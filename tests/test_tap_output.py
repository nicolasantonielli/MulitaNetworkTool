import json
import unittest
from types import SimpleNamespace
from pathlib import Path
import tempfile

from tests.qt_support import qt_app

from mulita.config import AppConfig
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.network import TapController
from mulita.ui.qt.dispatcher import QtDispatcher


class TapOutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = AppConfig(capture_dir=Path(temporary.name))
        self.controller = TapController(
            BridgeContext(self.config, None, QtDispatcher(), Notifier()),
            SimpleNamespace(is_running=False))

    def test_raw_lines_keep_arrival_order_and_hide_the_folder(self):
        self.controller._output(str(self.config.capture_dir / 'tap') + '/sesion.pcap: listening on br-mulita\n')
        self.controller._output('tcpdump: 2 packets captured\n')
        lines = json.loads(self.controller.linesJson)
        self.assertEqual(lines, [
            'sesion.pcap: listening on br-mulita',
            'tcpdump: 2 packets captured',
        ])
