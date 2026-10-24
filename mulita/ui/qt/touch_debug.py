"""Registro del tactil y correccion de saltos del ft5x06.

El controlador a veces manda un solo movimiento a coordenadas imposibles
(por ejemplo de 664,222 a -1220,88). Qt suelta el dedo ahi y el toque se pierde.
Ese salto se reemplaza por la ultima posicion valida.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from PyQt5.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt
from PyQt5.QtGui import QMouseEvent

log = logging.getLogger('mulita.touch')

# Un dedo no cruza media pantalla en un solo reporte. Mas que esto es un salto del driver.
_JUMP = 280

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
        self._anchor: tuple[float, float] | None = None
        self._rewriting = False
        self._seen: tuple | None = None

    def eventFilter(self, watched, event):
        if self._rewriting:
            return False
        kind = _MOUSE.get(event.type())
        if kind is not None:
            return self._mouse(watched, event, kind)
        touch = _TOUCH.get(event.type())
        if touch is not None:
            return self._touch(watched, event, touch)
        return False

    def _mouse(self, watched, event, kind: str) -> bool:
        position = event.globalPos()
        x, y = position.x(), position.y()
        if kind != 'press' and self._anchor is not None and _far(self._anchor, x, y):
            fixed_x, fixed_y = self._anchor
            self._log(kind, x, y, _target(watched), note=f'corregido {fixed_x:.0f},{fixed_y:.0f}')
            self._send_mouse(watched, event, fixed_x, fixed_y)
            return True
        self._anchor = (x, y)
        if kind != 'move' or self._due():
            source = _SOURCE.get(int(event.source()), str(int(event.source())))
            self._log(f'mouse {kind} {source}', x, y, _target(watched), button=int(event.button()))
        return False

    def _touch(self, watched, event, kind: str) -> bool:
        eaten = False
        target = _target(watched)
        for point in event.touchPoints():
            position = point.screenPos()
            x, y = position.x(), position.y()
            state = _POINT.get(int(point.state()), str(int(point.state())))
            if state == 'down' or self._anchor is None:
                self._anchor = (x, y)
            elif _far(self._anchor, x, y):
                self._log(f'touch {kind} id={point.id()} {state}', x, y, target, note='salto ignorado')
                eaten = True
                continue
            else:
                self._anchor = (x, y)
            if state == 'move' and not self._due():
                continue
            self._log(f'touch {kind} id={point.id()} {state}', x, y, target)
        return eaten

    def _send_mouse(self, watched, event, x: float, y: float) -> None:
        delta = QPointF(x - event.globalPos().x(), y - event.globalPos().y())
        fixed = QMouseEvent(
            event.type(), event.localPos() + delta, QPointF(x, y),
            event.button(), event.buttons(), event.modifiers())
        self._rewriting = True
        try:
            QCoreApplication.sendEvent(watched, fixed)
        finally:
            self._rewriting = False

    def _log(self, kind: str, x: float, y: float, target: str,
             button: int | None = None, note: str = '') -> None:
        key = (kind, round(x), round(y), note)
        now = time.monotonic()
        if self._seen is not None and self._seen[0] == key and now - self._seen[1] < 0.03:
            return
        self._seen = (key, now)
        extra = f' boton={button}' if button is not None else ''
        suffix = f' {note}' if note else ''
        log.info('%s %d,%d objetivo=%s%s%s', kind, x, y, target, extra, suffix)

    def _due(self) -> bool:
        now = time.monotonic()
        if now - self._last_move < 0.08:
            return False
        self._last_move = now
        return True


def _far(anchor: tuple[float, float], x: float, y: float) -> bool:
    return abs(x - anchor[0]) > _JUMP or abs(y - anchor[1]) > _JUMP


def _target(watched) -> str:
    object_name = getattr(watched, 'objectName', lambda: '')()
    if object_name:
        return object_name
    meta = getattr(watched, 'metaObject', None)
    return meta().className() if meta else type(watched).__name__
