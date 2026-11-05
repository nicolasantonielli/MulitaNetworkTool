import concurrent.futures
import http.client
import json
import tempfile
import threading
import unittest
from unittest.mock import patch

from tests.qt_support import qt_app
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QImage
from PyQt5.QtQml import QQmlComponent, QQmlEngine
from PyQt5.QtTest import QTest
from mulita.servers.web import Handler, Server
from mulita.ui.qt.bridge.remote import RemoteControl


class RemoteControlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        self.engine = QQmlEngine()
        component = QQmlComponent(self.engine)
        component.setData(b'''import QtQuick 2.15
import QtQuick.Window 2.15
Window {
    id: window
    width: 200; height: 120; visible: true; color: "white"
    property int clicks: 0
    property int moves: 0
    property int holds: 0
    property int angle: 0
    Rectangle {
        width: 40; height: 20; x: 145; y: 35; color: "red"
        rotation: window.angle
        MouseArea {
            anchors.fill: parent
            onClicked: clicks++
            onPressAndHold: holds++
            onPositionChanged: if (pressed) moves++
        }
    }
}''', QUrl())
        self.assertFalse(component.errors(), str(component.errors()))
        self.window = component.create()
        self.addCleanup(self.window.close)
        QTest.qWait(50)
        self.remote = RemoteControl(lambda: self.window)
        self.addCleanup(self.remote.close)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.server = Server(('127.0.0.1', 0), Handler, directory.name, '')
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(2)))
        self.pool = concurrent.futures.ThreadPoolExecutor(1)
        self.addCleanup(self.pool.shutdown)

    def post(self, action, token='', **data):
        def request():
            conn = http.client.HTTPConnection(*self.server.server_address, timeout=4)
            try:
                conn.request('POST', '/control/' + action, json.dumps(data), {
                    'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
                response = conn.getresponse()
                return response.status, response.read()
            finally:
                conn.close()
        future = self.pool.submit(request)
        while not future.done():
            QTest.qWait(10)
        return future.result()

    def test_pair_capture_and_control_rotated_item_over_http(self):
        self.assertEqual(self.post('frame')[0], 403)
        self.remote.setEnabled(True)
        code = self.remote.code
        self.assertEqual(self.post('pair', code='wrong')[0], 403)
        status, raw = self.post('pair', code=code)
        self.assertEqual(status, 200)
        token = raw.decode()
        self.assertEqual(self.remote.code, '')
        self.assertEqual(self.post('pair', code=code)[0], 403)
        self.assertEqual(self.post('frame', 'wrong')[0], 403)
        self.window.setProperty('angle', 90)
        for _ in range(10):
            status, frame = self.post('frame', token)
            if status == 200:
                break
            QTest.qWait(50)
        image = QImage.fromData(frame)
        self.assertEqual((image.width(), image.height()), (200, 120))
        self.assertGreater(image.pixelColor(165, 30).red(), 200)
        self.assertLess(image.pixelColor(165, 30).blue(), 50)
        # This point belongs to the rotated rectangle but lies outside its original bounds.
        point = dict(x=165/199, y=30/119)
        self.assertEqual(self.post('input', token, kind='down', **point)[0], 200)
        self.assertEqual(self.post('input', token, kind='up', **point)[0], 200)
        self.assertEqual(self.window.property('clicks'), 1)
        self.post('input', token, kind='down', **point)
        QTest.qWait(1000)
        self.assertEqual(self.window.property('holds'), 1)
        self.post('input', token, kind='move', x=0.8, y=0.36)
        self.assertGreater(self.window.property('moves'), 0)
        self.post('input', token, kind='cancel')
        self.assertEqual(self.post('input', token, kind='up', **point)[0], 409)
        self.remote.setEnabled(False)
        self.assertEqual(self.post('frame', token)[0], 403)
        self.assertEqual(self.post('input', token, kind='down', **point)[0], 403)

    def test_codes_expire_and_failed_pairings_lock_control(self):
        with patch('mulita.ui.qt.bridge.remote.time.monotonic', return_value=10):
            self.remote.setEnabled(True)
            code = self.remote.code
        with patch('mulita.ui.qt.bridge.remote.time.monotonic', return_value=131):
            self.assertEqual(self.post('pair', code=code)[0], 403)
        self.remote.setEnabled(True)
        for _ in range(5):
            self.assertEqual(self.post('pair', code='wrong')[0], 403)
        self.assertFalse(self.remote.enabled)
