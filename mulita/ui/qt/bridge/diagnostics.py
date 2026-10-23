from __future__ import annotations

from PyQt5.QtCore import pyqtProperty, pyqtSlot

from mulita.core.models import PING_COUNT, PING_INTERVAL, PING_SIZE, Range
from mulita.presentation import texts
from mulita.ui.qt.bridge.base import (BridgeContext, SessionController,
                                      TaskController)


def _limits(limits: Range) -> dict:
    return {'min': limits.minimum, 'max': limits.maximum, 'default': limits.default}


class TraceController(TaskController):

    @pyqtSlot(str)
    def trace(self, target: str) -> None:
        self._console.show(texts.TRACING)
        self._task(lambda: self._services.trace.trace(target),
                   self._console.append, lambda error: self._console.show(f'{error}\n'))


class PingController(SessionController):

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx, ctx.services.ping)

    @pyqtProperty('QVariantMap', constant=True)
    def limits(self) -> dict:
        return {'count': _limits(PING_COUNT), 'interval': _limits(PING_INTERVAL), 'size': _limits(PING_SIZE)}

    @pyqtSlot(str, float, float, float, result=bool)
    def start(self, target: str, count: float, interval: float, size: float) -> bool:
        self._console.clear()
        return self._launch(lambda **listeners: self._session.start(target, count, interval, size, **listeners))


class PortScanController(TaskController):

    @pyqtSlot(str)
    def scan(self, arguments: str) -> None:
        self._console.show(texts.SCANNING)
        self._task(lambda: self._services.port_scan.scan(arguments),
                   self._console.show, lambda error: self._console.show(f'{error}\n'))


class DiscoveryController(SessionController):

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx, ctx.services.discovery)

    @pyqtSlot(result=bool)
    def start(self) -> bool:
        self._console.clear()
        return self._launch(self._session.start)
