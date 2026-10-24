"""Registro del tactil y correccion del ft5x06.

Con el dedo quieto el panel manda un toque completo cada ~25 ms, siempre en
el mismo pixel, y a veces sigue despues de soltar. Eso se junta en un solo
apoyo: el boton queda presionado y se suelta una vez, donde empezo.

Un salto a coordenadas imposibles no se entrega. Tragar el evento tactil
crudo deja el dedo apretado para Qt, asi que esos solo se registran.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from PyQt5.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt, QTimer
from PyQt5.QtGui import QMouseEvent

log = logging.getLogger('mulita.touch')

# Un dedo no cruza media pantalla en un solo reporte. Mas que esto es un salto del driver.
_JUMP = 280
# El ft5x06, con el dedo quieto, manda un toque nuevo cada ~25 ms. Si el
# siguiente empieza cerca y antes de este plazo, es el mismo apoyo.
_BURST_MS = 90
_BURST_PX = 45

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
        self._down: tuple[float, float] | None = None
        self._press = None
        self._pending = None
        self._touch_pos: tuple[float, float] | None = None
        self._touch_at = 0.0
        self._burst = QTimer(self)
        self._burst.setSingleShot(True)
        self._burst.setInterval(_BURST_MS)
        self._burst.timeout.connect(self._flush)

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
        if kind == 'press':
            if self._press is not None and self._down is not None and _near(self._down, x, y):
                self._pending = self._press
                self._burst.start()
                return True
            self._flush()
            self._down = (x, y)
            self._anchor = (x, y)
            self._press = (
                watched, QPointF(event.localPos()), QPointF(x, y),
                event.button(), event.modifiers())
            self._log('mouse press', x, y, _target(watched), button=int(event.button()))
            return False
        if kind == 'release':
            # Se suelta donde apoyo. El reporte de soltar a veces cae en otro lado.
            self._pending = self._press or (
                watched, QPointF(event.localPos()), QPointF(x, y),
                event.button(), event.modifiers())
            self._burst.start()
            return True
        if self._anchor is not None and _far(self._anchor, x, y):
            return True
        self._anchor = (x, y)
        if self._due():
            source = _SOURCE.get(int(event.source()), str(int(event.source())))
            self._log(f'mouse {kind} {source}', x, y, _target(watched))
        return False

    def _flush(self) -> None:
        if self._pending is None:
            self._pending = self._press
        pending = self._pending
        self._pending = None
        self._press = None
        self._down = None
        if pending is None:
            return
        watched, local, screen, button, modifiers = pending
        try:
            from PyQt5 import sip
        except ImportError:
            sip = None
        if sip is not None and sip.isdeleted(watched):
            return
        self._log('mouse release', screen.x(), screen.y(), _target(watched), button=int(button))
        fixed = QMouseEvent(
            QEvent.MouseButtonRelease, local, screen, button, Qt.NoButton, modifiers)
        self._rewriting = True
        try:
            QCoreApplication.sendEvent(watched, fixed)
        finally:
            self._rewriting = False

    def _touch(self, watched, event, kind: str) -> bool:
        """Solo registra. Tragar un evento tactil deja el dedo "apretado" para Qt
        y el toque siguiente no llega."""
        target = _target(watched)
        now = time.monotonic()
        for point in event.touchPoints():
            position = point.screenPos()
            x, y = position.x(), position.y()
            state = _POINT.get(int(point.state()), str(int(point.state())))
            repeated = (
                self._touch_pos is not None
                and _near(self._touch_pos, x, y)
                and now - self._touch_at < 0.5
            )
            if repeated or (state == 'move' and not self._due()):
                continue
            self._touch_pos = (x, y)
            self._touch_at = now
            note = 'salto' if self._anchor is not None and _far(self._anchor, x, y) else ''
            self._log(f'touch {kind} id={point.id()} {state}', x, y, target, note=note)
        return False

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


def _near(anchor: tuple[float, float], x: float, y: float) -> bool:
    return abs(x - anchor[0]) <= _BURST_PX and abs(y - anchor[1]) <= _BURST_PX


def _target(watched) -> str:
    object_name = getattr(watched, 'objectName', lambda: '')()
    if object_name:
        return object_name
    meta = getattr(watched, 'metaObject', None)
    return meta().className() if meta else type(watched).__name__
