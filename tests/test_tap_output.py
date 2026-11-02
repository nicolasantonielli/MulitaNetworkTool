import json
import unittest
from types import SimpleNamespace
from pathlib import PurePosixPath

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
        self.controller = TapController(BridgeContext(config=AppConfig(capture_dir=PurePosixPath('/root/capturas')), settings=getattr(SimpleNamespace(tap=SimpleNamespace(is_running=False)), 'settings', None), dispatcher=QtDispatcher(), notifier=Notifier()), getattr(SimpleNamespace(tap=SimpleNamespace(is_running=False)), 'tap', None))

    def test_raw_lines_keep_arrival_order_and_hide_the_folder(self):
        self.controller._output('/root/capturas/tap/sesion.pcap: listening on br-mulita\n')
        self.controller._output('tcpdump: 2 packets captured\n')
        lines = json.loads(self.controller.linesJson)
        self.assertEqual(lines, [
            'sesion.pcap: listening on br-mulita',
            'tcpdump: 2 packets captured',
        ])
