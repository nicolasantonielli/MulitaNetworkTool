import unittest
from pathlib import Path

from tests.qt_support import qt_app
from PyQt5.QtCore import QObject, QUrl, QTimer
from PyQt5.QtQml import QQmlComponent, QQmlEngine
from PyQt5.QtQuick import QQuickItem
from PyQt5.QtTest import QTest, QSignalSpy
from mulita.config import Binaries
from mulita.core.commands import CommandFactory
from mulita.services.diagnostics import PingService
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.diagnostics import PingController
from mulita.ui.qt.dispatcher import QtDispatcher
from tests.fakes import FakeRunner


class PingControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        self.runner = FakeRunner()
        self.service = PingService(self.runner, CommandFactory(Binaries()))
        self.controller = PingController(
            BridgeContext(None, None, QtDispatcher(), Notifier()), self.service)
        self.controller.start('8.8.8.8', 0, 0.1, 64)

    def output(self, seq, newline='\n'):
        self.runner.outputs[-1](f'64 bytes from 8.8.8.8: icmp_seq={seq} ttl=64 time=1.2 ms{newline}')
        self.app.processEvents()

    def test_long_run_inserts_without_reset_and_can_stop(self):
        model = self.controller.repliesModel
        resets = QSignalSpy(model.modelReset)
        inserts = QSignalSpy(model.rowsInserted)
        for seq in range(1, 2001):
            self.output(seq)
        self.assertEqual(model.rowCount(), 2000)
        self.assertEqual(len(resets), 0)
        self.assertEqual(len(inserts), 2000)
        self.assertEqual(str(model.data(model.index(0), model.ReplyRole)['seq']), '2000')
        self.assertEqual(str(model.data(model.index(1999), model.ReplyRole)['seq']), '1')
        QTimer.singleShot(0, self.controller.stop)
        self.app.processEvents()
        self.assertEqual(self.runner.handles[-1].signals, ['INT'])
        self.assertFalse(self.controller.running)
        self.assertEqual(len(self.controller._replies), 2000)
        self.controller.clear()
        self.assertEqual(model.rowCount(), 0)

    def test_partial_output_and_restart(self):
        self.output(1, '')
        self.assertEqual(self.controller.repliesModel.rowCount(), 0)
        self.runner.handles[-1].finish()
        self.app.processEvents()
        self.assertEqual(self.controller.repliesModel.rowCount(), 1)
        self.assertTrue(self.controller.start('8.8.8.8', 0, 1, 64))
        self.output(2)
        self.assertFalse(self.controller.start('8.8.4.4', 0, 1, 64))
        self.assertEqual(self.controller.repliesModel.rowCount(), 1)

    def test_production_list_virtualizes_long_history(self):
        page = Path(__file__).resolve().parents[1] / 'mulita/ui/qt/qml/pages/TracesPage.qml'
        source = page.read_text()
        start = source.index('                        ListView {\n                            id: pingTable')
        end = source.index('\n                    }\n                }\n\n                Rectangle {\n                    id: statsBox', start)
        table = source[start:end]
        engine = QQmlEngine()
        engine.rootContext().setContextProperty('ping', self.controller)
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(page)))
        self.assertEqual(component.status(), QQmlComponent.Ready,
                         [e.toString() for e in component.errors()])
        component.setData(('''import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
ApplicationWindow {
    id: pingPage
    visible: true
    width: 600; height: 300
    property var columns: [{key: "seq", share: 100}]
    function columnWidth(share) { return 500 * share / 100 }
    function statusText(reply) { return reply.status }
    QtObject {
        id: ui
        property real gap: 4
        property real mm: 4
        property real fontSmall: 14
        property string surfaceAlt: "gray"
        property string danger: "red"
        property string warning: "orange"
        property string text: "black"
        property string monoFamily: "monospace"
    }
''' + table + '\n}').encode(), QUrl.fromLocalFile(str(page)))
        root = component.create()
        self.assertIsNotNone(root, [e.toString() for e in component.errors()])
        view = root.findChild(QObject, 'pingTable')
        view.setProperty('width', 600)
        view.setProperty('height', 300)
        for seq in range(1, 1001):
            self.output(seq)
        QTest.qWait(30)
        self.assertEqual(view.property('count'), 1000)
        content = view.property('contentItem')
        rows = [item for item in content.childItems() if item.property('reply') is not None]
        self.assertGreater(len(rows), 0)
        self.assertLess(len(rows), 40)
        root.close()
        root.deleteLater()
        self.app.processEvents()


if __name__ == '__main__':
    unittest.main()

