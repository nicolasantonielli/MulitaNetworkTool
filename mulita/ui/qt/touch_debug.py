"""Registro del tactil y correccion de saltos aislados en eventos sintetizados.

Cada pulsacion completa se entrega a Qt, incluso al repetir en el mismo punto.
El mouse real y los eventos tactiles crudos conservan su comportamiento nativo.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from PyQt5.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt
from PyQt5.QtGui import QMouseEvent, QWindow

log = logging.getLogger('mulita.touch')

# Un dedo no cruza media pantalla en un solo reporte. Mas que esto es un salto del driver.
_JUMP = 280
# Solo se usa para limitar mensajes repetidos del registro.
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


def real_mouse_names(text: str) -> list[str]:
    """Mouses de puntero. El ft5x06 tambien tiene un nodo mouse y no cuenta."""
    found = []
    name = ''
    for line in text.splitlines():
        if line.startswith('N: Name='):
            name = line.split('=', 1)[1].strip().strip('"')
        elif line.startswith('H: Handlers=') and name:
            handlers = line.split('=', 1)[1].split()
            if any(handler.startswith('mouse') for handler in handlers) and 'ft5x06' not in name.lower():
                found.append(name)
            name = ''
    return found


def connected_mice() -> list[str]:
    devices = Path('/proc/bus/input/devices')
    if not devices.exists():
        return []
    return real_mouse_names(devices.read_text(encoding='utf-8', errors='replace'))


class TouchDebug(QObject):

    def __init__(self):
        super().__init__()
        self._last_move = 0.0
        self._anchor: tuple[float, float] | None = None
        self._rewriting = False
        self._seen: tuple | None = None
        self._press = None
        self._touch_pos: tuple[float, float] | None = None
        self._touch_at = 0.0

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
        # La ventana reparte el evento a cada item y el filtro lo vuelve a ver.
        # Un release mandado directo al item deja a la ventana con el boton
        # tomado, y el proximo toque cae en la tecla anterior.
        if not isinstance(watched, QWindow):
            return False
        # Qt distingue el mouse fisico de los eventos derivados del tactil.
        # No modificar un mouse real ni gestos de otros botones.
        if event.source() == Qt.MouseEventNotSynthesized:
            return False
        if kind in ('press', 'release') and event.button() != Qt.LeftButton:
            return False
        position = event.globalPos()
        x, y = position.x(), position.y()
        if kind == 'press':
            if self._press is not None:
                self._send_release(self._press)
            self._anchor = (x, y)
            self._press = self._snapshot(watched, event)
            self._log('mouse press', x, y, _target(watched), button=int(event.button()))
            return False
        if kind == 'release':
            pending = self._press
            self._press = None
            anchor = self._anchor
            self._anchor = None
            # Conservar la posicion real al soltar un slider o una seleccion.
            # Solo corregir un salto imposible al ultimo punto valido.
            if pending is not None and anchor is not None and _far(anchor, x, y):
                self._send_release(pending)
                return True
            return False
        if self._press is not None:
            if self._anchor is not None and _far(self._anchor, x, y):
                return True
            self._anchor = (x, y)
            self._press = self._snapshot(watched, event)
        if self._due():
            source = _SOURCE.get(int(event.source()), str(int(event.source())))
            self._log(f'mouse {kind} {source}', x, y, _target(watched))
        return False

    @staticmethod
    def _snapshot(watched, event):
        return (watched, QPointF(event.localPos()), QPointF(event.screenPos()),
                Qt.LeftButton, event.modifiers(), event.source())

    def _send_release(self, pending) -> None:
        watched, local, screen, button, modifiers, source = pending
        try:
            from PyQt5 import sip
        except ImportError:
            sip = None
        if sip is not None and sip.isdeleted(watched):
            return
        self._log('mouse release', screen.x(), screen.y(), _target(watched), button=int(button))
        fixed = QMouseEvent(
            QEvent.MouseButtonRelease, local, local, screen, button, Qt.NoButton, modifiers, source)
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
            if state == 'move' and not self._due():
                continue
            repeated = (
                self._touch_pos is not None
                and _near(self._touch_pos, x, y)
                and now - self._touch_at < 0.5
            )
            if repeated:
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
