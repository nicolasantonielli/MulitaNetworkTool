"""Observacion de la entrada recibida por Qt, antes de las correcciones de Mulita."""
from collections import deque
import time

from PyQt5.QtCore import QObject, QEvent, Qt, QTimer, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QWindow


class TouchTest(QObject):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._active = False
        self._bypass = False
        self._events = deque(maxlen=200)
        self._counts = {}
        self._started = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self.changed.emit)

    @pyqtProperty(bool, notify=changed)
    def active(self):
        return self._active

    @pyqtProperty(bool, notify=changed)
    def bypass(self):
        return self._bypass

    @pyqtProperty('QVariantMap', notify=changed)
    def counts(self):
        return dict(self._counts)

    @pyqtProperty('QVariantList', notify=changed)
    def events(self):
        return list(self._events)

    @pyqtProperty('QVariantMap', notify=changed)
    def latest(self):
        return dict(self._events[-1]) if self._events else {}

    @pyqtSlot(bool)
    def setActive(self, value):
        self._active = value
        if not value:
            self._bypass = False
        self.changed.emit()

    @pyqtSlot(bool)
    def setBypass(self, value):
        self._bypass = bool(value) and self._active
        self.changed.emit()

    @pyqtSlot()
    def clear(self):
        self._events.clear()
        self._counts.clear()
        self._started = time.monotonic()
        self.changed.emit()

    def observe(self, watched, event):
        if not self._active or not isinstance(watched, QWindow):
            return
        kind = event.type()
        phases = {QEvent.TouchBegin: 'down', QEvent.TouchUpdate: 'move',
                  QEvent.TouchEnd: 'up', QEvent.TouchCancel: 'cancel'}
        if kind in phases:
            phase = phases[kind]
            self._count('touch_' + phase)
            for point in event.touchPoints():
                states = {Qt.TouchPointPressed: 'down', Qt.TouchPointReleased: 'up',
                          Qt.TouchPointMoved: 'move', Qt.TouchPointStationary: 'still'}
                self._record('touch', states.get(point.state(), phase),
                             point.screenPos(), point.id())
            if not event.touchPoints():
                self._record('touch', phase, None, -1)
        elif kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease,
                      QEvent.MouseButtonDblClick, QEvent.MouseMove):
            if kind == QEvent.MouseMove and not event.buttons():
                return
            phase = {QEvent.MouseButtonPress: 'down', QEvent.MouseButtonRelease: 'up',
                     QEvent.MouseButtonDblClick: 'double', QEvent.MouseMove: 'move'}[kind]
            self._count('mouse_' + phase)
            source = {Qt.MouseEventNotSynthesized: 'mouse',
                      Qt.MouseEventSynthesizedByQt: 'qt',
                      Qt.MouseEventSynthesizedBySystem: 'system',
                      Qt.MouseEventSynthesizedByApplication: 'app'}.get(event.source(), 'unknown')
            self._record(source, phase, event.screenPos(), -1)
        else:
            return
        if not self._timer.isActive():
            self._timer.start()

    def _count(self, key):
        self._counts[key] = self._counts.get(key, 0) + 1

    def _record(self, source, phase, position, point_id):
        self._events.append({
            'source': source, 'phase': phase, 'id': point_id,
            'x': position.x() if position is not None else -1,
            'y': position.y() if position is not None else -1,
            'ms': round((time.monotonic() - self._started) * 1000),
        })
