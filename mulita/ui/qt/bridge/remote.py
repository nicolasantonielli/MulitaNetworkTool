"""Remote access to the live Qt window. All input and capture run on the GUI thread."""
import json
import os
import secrets
import time

from PyQt5 import sip
from PyQt5.QtCore import (QBuffer, QCoreApplication, QEvent, QIODevice, QObject,
                          QPointF, Qt, QTimer, pyqtProperty, pyqtSignal, pyqtSlot)
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtNetwork import QHostAddress, QTcpServer
from PyQt5.QtQuick import QQuickWindow


class RemoteControl(QObject):
    changed = pyqtSignal()

    def __init__(self, window):
        super().__init__()
        self._window = window
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._accept)
        if self._server.listen(QHostAddress.LocalHost, 0):
            os.environ['MULITA_CONTROL_PORT'] = str(self._server.serverPort())
        self._code = self._token = ''
        self._expires = self._last_frame = self._last_input = 0
        self._attempts = 0
        self._pressed = False
        self._frame = b''
        self._grab = None
        self._watch = QTimer(self)
        self._watch.setInterval(1000)
        self._watch.timeout.connect(self._expire)

    @pyqtProperty(bool, constant=True)
    def available(self):
        return self._server.isListening()

    @pyqtProperty(bool, notify=changed)
    def enabled(self):
        return bool(self._code or self._token)

    @pyqtProperty(str, notify=changed)
    def code(self):
        return self._code

    @pyqtSlot(bool)
    def setEnabled(self, enabled):
        self._code = self._token = ''
        self._cancel()
        self._frame = b''
        self._grab = None
        self._attempts = 0
        if enabled and self.available:
            self._code = f'{secrets.randbelow(1000000):06d}'
            self._expires = time.monotonic() + 120
            self._watch.start()
        else:
            self._watch.stop()
        self.changed.emit()

    def close(self):
        self.setEnabled(False)
        if os.environ.get('MULITA_CONTROL_PORT') == str(self._server.serverPort()):
            os.environ.pop('MULITA_CONTROL_PORT', None)
        self._server.close()

    def _expire(self):
        now = time.monotonic()
        if self.enabled and now >= self._expires:
            self.setEnabled(False)
        elif self._pressed and now - self._last_input > 4:
            self._cancel()

    def _accept(self):
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            sock.setReadBufferSize(2049)
            sock.readyRead.connect(lambda s=sock: self._receive(s))
            sock.disconnected.connect(sock.deleteLater)
            timeout = QTimer(sock)
            timeout.setSingleShot(True)
            timeout.timeout.connect(sock.abort)
            timeout.start(4000)
            if sock.bytesAvailable():
                self._receive(sock)

    def _receive(self, sock):
        if not sock.canReadLine():
            if sock.bytesAvailable() > 2048:
                sock.abort()
            return
        try:
            message = json.loads(bytes(sock.readLine(2049)))
            status, body = self._request(message)
        except (ValueError, TypeError, AttributeError):
            status, body = 400, b''
        sock.write(str(status).encode() + b'\n' + body)
        sock.disconnectFromHost()

    def _request(self, msg):
        self._expire()
        if not self.enabled:
            return 403, b''
        action = msg.get('action')
        if action == 'pair':
            if not self._code:
                return 403, b''
            if not secrets.compare_digest(str(msg.get('code', '')).encode(), self._code.encode()):
                self._attempts += 1
                if self._attempts >= 5:
                    self.setEnabled(False)
                return 403, b''
            self._code = ''
            self._token = secrets.token_urlsafe(32)
            self._expires = time.monotonic() + 30
            self.changed.emit()
            return 200, self._token.encode()
        if not self._token or not secrets.compare_digest(str(msg.get('token', '')).encode(), self._token.encode()):
            return 403, b''
        if action == 'end':
            self.setEnabled(False)
            return 200, b''
        if action == 'frame':
            # A lost browser stops polling. Revoke its session after 30 seconds.
            self._expires = time.monotonic() + 30
            return self._capture()
        if action == 'input':
            return self._input(msg)
        return 400, b''

    def _capture(self):
        now = time.monotonic()
        if self._grab is None and now - self._last_frame >= 0.25:
            self._last_frame = now
            grab = sip.cast(self._window(), QQuickWindow).contentItem().grabToImage()
            if grab is None:
                return 503, b''
            self._grab = grab
            grab.ready.connect(self._captured)
        return (200, self._frame) if self._frame else (202, b'')

    def _captured(self):
        grab = self.sender()
        if grab is not self._grab:
            return
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        if grab.image().save(buffer, 'JPEG', 70):
            self._frame = bytes(buffer.data())
        self._grab = None

    def _input(self, msg):
        kind = msg.get('kind')
        if kind == 'cancel':
            self._cancel()
            return 200, b''
        x, y = msg.get('x'), msg.get('y')
        if kind not in ('down', 'move', 'up') or not all(
                type(n) in (float, int) and 0 <= n <= 1 for n in (x, y)):
            return 400, b''
        if (kind == 'down') == self._pressed:
            return 409, b''
        window = self._window()
        point = QPointF(x * (window.width() - 1), y * (window.height() - 1))
        self._last_input = time.monotonic()
        self._pressed = kind != 'up'
        self._mouse(window, kind, point)
        return 200, b''

    def _cancel(self):
        if self._pressed:
            self._pressed = False
            window = self._window()
            outside = QPointF(-100, -100)
            self._mouse(window, 'move', outside)
            self._mouse(window, 'up', outside)

    @staticmethod
    def _mouse(window, kind, point):
        event = {'down': QEvent.MouseButtonPress, 'move': QEvent.MouseMove, 'up': QEvent.MouseButtonRelease}[kind]
        button = Qt.NoButton if kind == 'move' else Qt.LeftButton
        buttons = Qt.NoButton if kind == 'up' else Qt.LeftButton
        mouse = QMouseEvent(event, point, point, QPointF(window.mapToGlobal(point.toPoint())),
                            button, buttons, Qt.NoModifier)
        mouse.setTimestamp(int(time.monotonic() * 1000))
        QCoreApplication.sendEvent(window, mouse)
