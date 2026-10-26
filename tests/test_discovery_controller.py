import json
import unittest
from types import SimpleNamespace

from tests.qt_support import qt_app

from mulita.config import Binaries
from mulita.core.commands import CommandFactory
from mulita.core.models import CommandResult, MISSING_COMMAND_CODE
from mulita.presentation.i18n import tr, use
from mulita.services.diagnostics import DiscoveryService
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.diagnostics import DiscoveryController
from mulita.ui.qt.dispatcher import QtDispatcher
from tests.fakes import FakeRunner


class DiscoveryControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        use('es')
        addresses = json.dumps([{
            'ifname': 'eth0',
            'addr_info': [{'family': 'inet', 'local': '192.168.1.10', 'prefixlen': 24}],
        }])
        self.runner = FakeRunner({'/usr/bin/ip': CommandResult(0, addresses)})
        self.session = DiscoveryService(self.runner, CommandFactory(Binaries()))
        self.notifier = Notifier()
        self.toasts = []
        self.notifier.notified.connect(lambda *args: self.toasts.append(args))
        self.controller = DiscoveryController(BridgeContext(
            config=None, services=SimpleNamespace(discovery=self.session),
            dispatcher=QtDispatcher(), notifier=self.notifier))

    def output(self, text):
        self.runner.outputs[-1](text)
        self.app.processEvents()

    def finish(self, code):
        self.runner.handles[-1].finish(code)
        self.app.processEvents()

    def test_failure_shows_diagnostic_in_error_toast_and_keeps_hosts(self):
        self.assertTrue(self.controller.start('eth0'))
        self.output('192.168.1.1 aa:bb:cc:dd:ee:ff 1 60 Router\n')
        self.output('pcap_open_live: eth0: Permission denied\n')
        self.finish(1)
        self.assertFalse(self.controller.running)
        self.assertEqual(self.toasts, [(
            'error', tr('discoverTitle'), 'pcap_open_live: eth0: Permission denied')])
        self.assertEqual(len(json.loads(self.controller.hostsJson)), 1)

    def test_missing_command_includes_output_without_final_newline(self):
        self.controller.start('eth0')
        message = tr('missingCommand', name='/sbin/netdiscover')
        self.output(message)
        self.finish(MISSING_COMMAND_CODE)
        self.assertEqual(self.toasts[-1], ('error', tr('discoverTitle'), message))

    def test_failure_without_output_shows_exit_code(self):
        self.controller.start('eth0')
        self.finish(2)
        self.assertEqual(self.toasts[-1], (
            'error', tr('discoverTitle'), tr('discoverFailed', code=2)))

    def test_manual_stop_does_not_show_error(self):
        self.controller.start('eth0')
        self.output('Listening on eth0\n')
        self.controller.stop()
        self.app.processEvents()
        self.assertFalse(self.controller.running)
        self.assertEqual(self.toasts, [])

    def test_success_does_not_show_error(self):
        self.controller.start('eth0')
        self.output('Listening on eth0\n')
        self.finish(0)
        self.assertEqual(self.toasts, [])

    def test_next_run_resets_stop_flag_and_old_diagnostics(self):
        self.controller.start('eth0')
        self.output('old message\n')
        self.controller.stop()
        self.app.processEvents()
        self.controller.start('eth0')
        self.finish(3)
        self.assertEqual(self.toasts, [(
            'error', tr('discoverTitle'), tr('discoverFailed', code=3))])

    def test_invalid_interface_shows_error_without_launching(self):
        self.assertFalse(self.controller.start('../eth0'))
        self.assertEqual(self.runner.starts, [])
        self.assertEqual(self.toasts[0][0], 'error')

    def test_restarting_active_discovery_preserves_diagnostic(self):
        self.controller.start('eth0')
        self.output('Permission denied\n')
        self.assertFalse(self.controller.start('eth0'))
        self.finish(1)
        self.assertEqual(self.toasts[-1][2], 'Permission denied')


if __name__ == '__main__':
    unittest.main()
