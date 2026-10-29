import json
import time
import unittest
from types import SimpleNamespace

from tests.qt_support import qt_app
from tests.fakes import FakeRunner

from mulita.config import Binaries
from mulita.core.commands import CommandFactory
from mulita.core.models import CommandResult, MISSING_COMMAND_CODE
from mulita.presentation.i18n import tr, use
from mulita.services.servers import ServerService
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.servers import ServersController
from mulita.ui.qt.dispatcher import QtDispatcher

import tempfile
from pathlib import Path


class DeferredDispatcher:
    """Controla por separado la preparación y su respuesta a la interfaz."""

    def wrap(self, callback):
        return callback

    def background(self, task, success, failure):
        self.task, self.success, self.failure = task, success, failure


class ServersControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        use('es')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.runner = FakeRunner({'/usr/bin/ip': CommandResult(0, json.dumps([{
            'ifname': 'eth1', 'addr_info': [{'family': 'inet', 'local': '192.168.50.1', 'prefixlen': 24}]}]))})
        self.service = ServerService(self.runner, CommandFactory(Binaries()), root / 'servidores',
                                     root / 'estado', root / 'capturas', posix=True)
        self.notifier = Notifier()
        self.toasts = []
        self.notifier.notified.connect(lambda *args: self.toasts.append(args))
        self.controller = ServersController(BridgeContext(
            config=None, services=SimpleNamespace(servers=self.service),
            dispatcher=QtDispatcher(), notifier=self.notifier), clock=lambda: '10:00:00')

    def pump(self, condition, seconds=3):
        deadline = time.time() + seconds
        while time.time() < deadline:
            self.app.processEvents()
            if condition():
                return
            time.sleep(0.01)
        self.fail('La condicion no se cumplio a tiempo')

    def states(self):
        return json.loads(self.controller.statesJson)

    def start(self, kind='ntp', values=None):
        self.assertTrue(self.controller.start(kind, json.dumps(values or {})))
        self.pump(lambda: self.states().get(kind) == 'running' or self.toasts)

    def output(self, text):
        self.runner.outputs[-1](text)
        self.app.processEvents()

    def test_catalog_replaces_the_random_password_with_a_generated_one(self):
        catalog = json.loads(self.controller.catalogJson)
        sftp = next(item for item in catalog if item['id'] == 'sftp')
        password = next(field for field in sftp['fields'] if field['key'] == 'password')
        self.assertEqual(len(password['default']), 8)
        self.assertNotEqual(password['default'], '@random')
        self.assertEqual(json.loads(self.controller.catalogJson), catalog)

    def test_start_goes_through_starting_to_running_and_tracks_any_running(self):
        self.assertFalse(self.controller.anyRunning)
        self.assertTrue(self.controller.start('ntp', '{}'))
        self.assertEqual(self.states(), {'ntp': 'starting'})
        self.pump(lambda: self.states().get('ntp') == 'running')
        self.assertTrue(self.controller.anyRunning)

    def test_servers_run_side_by_side_and_stop_independently(self):
        self.start('ntp')
        self.start('iperf')
        self.assertEqual(self.states(), {'ntp': 'running', 'iperf': 'running'})
        self.controller.stop('ntp')
        self.app.processEvents()
        self.assertEqual(self.states(), {'iperf': 'running'})
        self.assertEqual(self.toasts, [])

    def test_starting_twice_is_ignored(self):
        self.start('ntp')
        self.assertFalse(self.controller.start('ntp', '{}'))
        self.assertEqual(len(self.runner.starts), 1)

    def test_stop_before_preparation_finishes_stops_the_eventual_process(self):
        dispatcher = DeferredDispatcher()
        self.controller._ctx.dispatcher = dispatcher
        self.assertTrue(self.controller.start('ntp', '{}'))
        self.controller.stop('ntp')
        self.assertEqual(self.states(), {'ntp': 'starting'})
        self.assertFalse(self.controller.start('ntp', '{}'))
        dispatcher.success(dispatcher.task())
        self.assertFalse(self.service.is_running('ntp'))
        self.assertEqual(self.states(), {})
        self.assertEqual(self.toasts, [])
        self.assertTrue(self.controller.start('ntp', '{}'))

    def test_stop_after_launch_but_before_start_callback_is_not_lost(self):
        dispatcher = DeferredDispatcher()
        self.controller._ctx.dispatcher = dispatcher
        self.controller.start('ntp', '{}')
        result = dispatcher.task()
        self.assertTrue(self.service.is_running('ntp'))
        self.controller.stop('ntp')
        dispatcher.success(result)
        self.assertFalse(self.service.is_running('ntp'))
        self.assertEqual(self.states(), {})
        self.assertEqual(self.toasts, [])

    def test_cancelled_preparation_failure_returns_to_idle(self):
        dispatcher = DeferredDispatcher()
        self.controller._ctx.dispatcher = dispatcher
        self.controller.start('iperf', '{"port":"abc"}')
        self.controller.stop('iperf')
        try:
            dispatcher.task()
        except Exception as error:
            dispatcher.failure(error)
        self.assertEqual(self.states(), {})
        self.assertEqual(self.runner.starts, [])
        self.assertEqual(self.toasts, [])
        self.assertFalse(self.controller._stopping)

    def test_early_exit_keeps_start_locked_until_preparation_returns(self):
        dispatcher = DeferredDispatcher()
        self.controller._ctx.dispatcher = dispatcher
        self.controller.start('ntp', '{}')
        result = dispatcher.task()
        self.runner.handles[-1].finish(2)
        self.assertFalse(self.controller.start('ntp', '{}'))
        dispatcher.success(result)
        self.assertEqual(self.states(), {})
        self.assertEqual(self.toasts[-1], ('error', tr('srvNtp'), tr('serverFailed', code=2)))

    def test_invalid_settings_show_an_error_and_leave_the_server_stopped(self):
        self.assertTrue(self.controller.start('iperf', json.dumps({'port': 'abc'})))
        self.pump(lambda: self.toasts)
        self.assertEqual(self.toasts[0][0], 'error')
        self.assertEqual(self.states(), {})
        self.assertEqual(self.runner.starts, [])

    def test_unknown_kind_and_garbage_values_are_handled(self):
        self.assertFalse(self.controller.start('ftp', '{}'))
        self.assertTrue(self.controller.start('ntp', 'no es json'))
        self.pump(lambda: self.states().get('ntp') == 'running')

    def test_log_rows_belong_to_the_selected_server_and_show_newest_first(self):
        self.controller.select('ntp')
        self.start('ntp')
        self.output('10.0.0.1\tHora entregada (NTPv4)\n10.0.0.2\tHora entregada (NTPv3)\n')
        rows = json.loads(self.controller.rowsJson)
        self.assertEqual([row['client'] for row in rows], ['10.0.0.2', '10.0.0.1'])
        self.assertEqual(rows[0]['time'], '10:00:00')
        self.controller.select('tftp')
        self.assertEqual(json.loads(self.controller.rowsJson), [])
        self.controller.select('ntp')
        self.assertEqual(len(json.loads(self.controller.rowsJson)), 2)

    def test_rows_notify_only_for_the_selected_server(self):
        changes = []
        self.controller.rowsChanged.connect(lambda: changes.append(1))
        self.controller.select('iperf')
        base = len(changes)
        self.start('ntp')
        self.output('1.1.1.1\tHora entregada (NTPv4)\n')
        self.assertEqual(len(changes), base)

    def test_a_new_start_clears_the_previous_log(self):
        self.controller.select('ntp')
        self.start('ntp')
        self.output('1.1.1.1\tHora entregada (NTPv4)\n')
        self.controller.stop('ntp')
        self.app.processEvents()
        self.start('ntp')
        self.assertEqual(json.loads(self.controller.rowsJson), [])

    def test_crash_shows_the_last_lines_in_an_error_toast(self):
        self.start('ntp')
        self.output('No se pudo abrir el puerto 123: Address already in use\n')
        self.runner.handles[-1].finish(1)
        self.app.processEvents()
        self.assertEqual(self.states(), {})
        self.assertEqual(self.toasts, [(
            'error', tr('srvNtp'), 'No se pudo abrir el puerto 123: Address already in use')])

    def test_crash_without_output_shows_the_exit_code(self):
        self.start('ntp')
        self.runner.handles[-1].finish(2)
        self.app.processEvents()
        self.assertEqual(self.toasts[-1], ('error', tr('srvNtp'), tr('serverFailed', code=2)))

    def test_manual_stop_does_not_show_an_error(self):
        self.start('ntp')
        self.controller.stop('ntp')
        self.app.processEvents()
        self.assertEqual(self.toasts, [])

    def test_missing_program_reports_which_one(self):
        self.start('iperf')
        message = tr('missingCommand', name='/usr/bin/iperf3')
        self.output(message)
        self.runner.handles[-1].finish(MISSING_COMMAND_CODE)
        self.app.processEvents()
        self.assertEqual(self.toasts[-1], ('error', tr('srvIperf'), message))

    def test_a_process_that_dies_instantly_never_stays_running(self):
        self.assertTrue(self.controller.start('ntp', '{}'))
        self.pump(lambda: len(self.runner.handles) == 1)
        self.runner.handles[-1].finish(1)
        self.pump(lambda: self.states() == {})
        self.assertFalse(self.controller.anyRunning)

    def test_save_writes_the_log_and_confirms(self):
        self.controller.select('ntp')
        self.start('ntp')
        self.output('1.1.1.1\tHora entregada (NTPv4)\n')
        self.controller.save('ntp', 'ntp-prueba')
        self.assertEqual(self.toasts[-1], ('success', tr('srvNtp'), 'ntp-prueba.csv'))
        self.controller.save('ntp', 'ntp-prueba')
        self.assertEqual(self.toasts[-1][0], 'error')

    def test_clear_empties_the_log(self):
        self.controller.select('ntp')
        self.start('ntp')
        self.output('1.1.1.1\tHora entregada (NTPv4)\n')
        self.controller.clear('ntp')
        self.assertEqual(json.loads(self.controller.rowsJson), [])


if __name__ == '__main__':
    unittest.main()
