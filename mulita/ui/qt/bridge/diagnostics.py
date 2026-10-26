from __future__ import annotations

import json

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.models import PING_COUNT, PING_INTERVAL, PING_SIZE, Range
from mulita.presentation import texts
from mulita.ui.qt.bridge.base import (BridgeContext, SessionController,
                                      TaskController)


def _limits(limits: Range) -> dict:
    return {'min': limits.minimum, 'max': limits.maximum, 'default': limits.default}


class TraceController(TaskController):
    hopsChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._hops: tuple = ()

    @pyqtProperty(str, notify=hopsChanged)
    def hopsJson(self) -> str:
        return json.dumps([{
            'hop': item.hop,
            'address': item.address,
            'loss': item.loss,
            'sent': item.sent,
            'last': item.last,
            'average': item.average,
            'best': item.best,
            'worst': item.worst,
            'deviation': item.deviation,
        } for item in self._hops])

    @pyqtSlot(str)
    def trace(self, target: str) -> None:
        self._task(lambda: self._services.trace.trace(target), self._show)

    @pyqtSlot()
    def clear(self) -> None:
        if self._busy:
            return
        self._hops = ()
        self.hopsChanged.emit()

    @pyqtSlot(str)
    def save(self, filename: str) -> None:
        hops = self._hops
        self._task(lambda: self._services.trace.save(hops, filename), self._saved)

    def _show(self, hops: tuple) -> None:
        self._hops = tuple(hops)
        self.hopsChanged.emit()
        if not self._hops:
            self._ctx.notifier.info('Trazas', 'No hubo saltos')

    def _saved(self, name: str) -> None:
        self._ctx.notifier.success('Trazas', name)


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
