"""Registro de lo que Qt recibe del tactil. Sirve para ver por que un toque cae mal."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from PyQt5.QtCore import QEvent, QObject, Qt

log = logging.getLogger('mulita.touch')

_MOUSE = {
    QEvent.MouseButtonPress: 'press',
    QEvent.MouseButtonRelease: 'release',
    QEvent.MouseMove: 'move',
}
_TOUCH = {
    QEvent.TouchBegin: 'begin',
    QEvent.TouchUpdate: 'update',
    QEvent.TouchEnd: 'end',
    QEvent.TouchCancel: 'cancel',
}
_POINT = {
    int(Qt.TouchPointPressed): 'down',
    int(Qt.TouchPointMoved): 'move',
    int(Qt.TouchPointStationary): 'still',
    int(Qt.TouchPointReleased): 'up',
}
_SOURCE = {
    int(Qt.MouseEventNotSynthesized): 'real',
    int(Qt.MouseEventSynthesizedBySystem): 'sistema',
    int(Qt.MouseEventSynthesizedByQt): 'qt',
    int(Qt.MouseEventSynthesizedByApplication): 'app',
}


def log_input_devices() -> None:
    """Lista los dispositivos de entrada del kernel. En la Pi suele haber dos para el mismo panel."""
    devices = Path('/proc/bus/input/devices')
    if not devices.exists():
        log.info('sin /proc/bus/input/devices')
        return
    name = ''
    for line in devices.read_text(encoding='utf-8', errors='replace').splitlines():
        if line.startswith('N: Name='):
            name = line.split('=', 1)[1].strip().strip('"')
        elif line.startswith('H: Handlers=') and name:
            log.info('entrada %s | %s', name, line.split('=', 1)[1].strip())
            name = ''


class TouchDebug(QObject):

    def __init__(self):
        super().__init__()
        self._last_move = 0.0

    def eventFilter(self, watched, event):
        kind = _MOUSE.get(event.type())
        if kind is not None:
            self._mouse(watched, event, kind)
        else:
            touch = _TOUCH.get(event.type())
            if touch is not None:
                self._touch(watched, event, touch)
        return False

    def _mouse(self, watched, event, kind: str) -> None:
        if kind == 'move' and not self._due():
            return
        position = event.globalPos()
        source = _SOURCE.get(int(event.source()), str(int(event.source())))
        log.info(
            'mouse %s %s %d,%d boton=%s objetivo=%s',
            kind, source, position.x(), position.y(),
            int(event.button()), _target(watched))

    def _touch(self, watched, event, kind: str) -> None:
        points = event.touchPoints()
        moving = points and all(int(point.state()) == int(Qt.TouchPointMoved) for point in points)
        if moving and not self._due():
            return
        target = _target(watched)
        for point in points:
            position = point.screenPos()
            state = _POINT.get(int(point.state()), str(int(point.state())))
            log.info(
                'touch %s id=%s %s %d,%d objetivo=%s',
                kind, point.id(), state, position.x(), position.y(), target)

    def _due(self) -> bool:
        now = time.monotonic()
        if now - self._last_move < 0.08:
            return False
        self._last_move = now
        return True


def _target(watched) -> str:
    name = ''
    object_name = getattr(watched, 'objectName', lambda: '')()
    if object_name:
        name = object_name
    meta = getattr(watched, 'metaObject', None)
    class_name = meta().className() if meta else type(watched).__name__
    return name or class_name
