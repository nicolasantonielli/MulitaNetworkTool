from __future__ import annotations

import json

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.errors import MulitaError
from mulita.core.models import PING_COUNT, PING_INTERVAL, PING_SIZE, PingSummary, Range
from mulita.core.parsers import parse_discovery_line, read_ping_line
from mulita.presentation import texts
from mulita.presentation.i18n import tr
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
            self._ctx.notifier.info(tr('tracesTitle'), tr('noHops'))

    def _saved(self, name: str) -> None:
        self._ctx.notifier.success(tr('tracesTitle'), name)


class PingController(SessionController):
    repliesChanged = pyqtSignal()
    summaryChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx, ctx.services.ping)
        self._replies: tuple = ()
        self._summary = PingSummary()
        self._pending = ''

    @pyqtProperty('QVariantMap', constant=True)
    def limits(self) -> dict:
        return {'count': _limits(PING_COUNT), 'interval': _limits(PING_INTERVAL), 'size': _limits(PING_SIZE)}

    @pyqtProperty(str, notify=repliesChanged)
    def repliesJson(self) -> str:
        return json.dumps([{
            'seq': item.seq,
            'source': item.source,
            'ttl': item.ttl,
            'time': item.time,
            'status': item.status,
            'detail': item.detail,
        } for item in reversed(self._replies)])

    @pyqtProperty(str, notify=summaryChanged)
    def summaryJson(self) -> str:
        item = self._summary
        if not item.ready and not item.target:
            return ''
        return json.dumps({
            'target': item.target,
            'transmitted': item.transmitted,
            'received': item.received,
            'loss': item.loss,
            'elapsed': item.elapsed,
            'minimum': item.minimum,
            'average': item.average,
            'maximum': item.maximum,
            'deviation': item.deviation,
            'ready': item.ready,
        })

    @pyqtSlot(str, float, float, float, result=bool)
    def start(self, target: str, count: float, interval: float, size: float) -> bool:
        self._replies = ()
        self._summary = PingSummary()
        self._pending = ''
        self.repliesChanged.emit()
        self.summaryChanged.emit()
        return self._launch(lambda **listeners: self._session.start(target, count, interval, size, **listeners))

    @pyqtSlot()
    def clear(self) -> None:
        if self._running:
            return
        self._replies = ()
        self._summary = PingSummary()
        self._pending = ''
        self.repliesChanged.emit()
        self.summaryChanged.emit()

    @pyqtSlot(str)
    def save(self, filename: str) -> None:
        if self._running:
            return
        try:
            name = self._services.ping.save(self._replies, self._summary, filename)
        except MulitaError as exc:
            self._fail(exc)
            return
        statics = name[:-4] + '.statics.csv' if name.endswith('.csv') else name
        self._ctx.notifier.success(tr('pingTitle'), tr('pingSaved', table=name, statics=statics))

    def _output(self, text: str) -> None:
        self._pending += text.replace('\r', '')
        while '\n' in self._pending:
            line, self._pending = self._pending.split('\n', 1)
            self._take(line)
        self.repliesChanged.emit()
        self.summaryChanged.emit()

    def _finished(self, _code: int) -> None:
        if self._pending.strip():
            self._take(self._pending)
            self._pending = ''
            self.repliesChanged.emit()
            self.summaryChanged.emit()

    def _take(self, line: str) -> None:
        reply, summary = read_ping_line(line, self._summary)
        self._summary = summary
        if reply is not None:
            self._replies = (*self._replies, reply)

    def _rejected(self, error: MulitaError) -> None:
        self._fail(error)


class PortScanController(TaskController):
    portsChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._ports: tuple = ()

    @pyqtProperty(str, notify=portsChanged)
    def portsJson(self) -> str:
        return json.dumps([{
            'host': item.host,
            'port': item.port,
            'protocol': item.protocol,
            'state': item.state,
            'service': item.service,
        } for item in self._ports])

    @pyqtSlot(str)
    def scan(self, arguments: str) -> None:
        self._task(lambda: self._services.port_scan.scan(arguments), self._show)

    @pyqtSlot()
    def clear(self) -> None:
        if self._busy:
            return
        self._ports = ()
        self.portsChanged.emit()

    @pyqtSlot(str)
    def save(self, filename: str) -> None:
        found = self._ports
        self._task(lambda: self._services.port_scan.save(found, filename), self._saved)

    def _show(self, found: tuple) -> None:
        self._ports = tuple(found)
        self.portsChanged.emit()
        if not self._ports:
            self._ctx.notifier.info(tr('scanTitle'), tr('noPorts'))

    def _saved(self, name: str) -> None:
        self._ctx.notifier.success(tr('scanTitle'), name)


class DiscoveryController(SessionController):
    hostsChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx, ctx.services.discovery)
        self._hosts: list = []
        self._pending = ''

    @pyqtProperty(str, notify=hostsChanged)
    def hostsJson(self) -> str:
        return json.dumps([{
            'ip': item.ip,
            'mac': item.mac,
            'count': item.count,
            'vendor': item.vendor,
        } for item in self._hosts])

    @pyqtSlot(str, result=bool)
    def start(self, interface: str) -> bool:
        self._hosts = []
        self._pending = ''
        self.hostsChanged.emit()
        return self._launch(lambda **callbacks: self._session.start(interface, **callbacks))

    @pyqtSlot()
    def clear(self) -> None:
        if self._running:
            return
        self._hosts = []
        self._pending = ''
        self.hostsChanged.emit()

    @pyqtSlot(str)
    def save(self, filename: str) -> None:
        if self._running:
            return
        found = tuple(self._hosts)
        try:
            name = self._services.discovery.save(found, filename)
        except MulitaError as exc:
            self._fail(exc)
            return
        self._ctx.notifier.success(tr('discoverTitle'), name)

    def _output(self, text: str) -> None:
        self._pending += text.replace('\r', '')
        while '\n' in self._pending:
            line, self._pending = self._pending.split('\n', 1)
            self._take(line)
        self.hostsChanged.emit()

    def _finished(self, _code: int) -> None:
        if self._pending.strip():
            self._take(self._pending)
            self._pending = ''
            self.hostsChanged.emit()

    def _take(self, line: str) -> None:
        found = parse_discovery_line(line)
        if found is None:
            return
        for index, item in enumerate(self._hosts):
            if item.ip == found.ip:
                self._hosts[index] = found
                return
        self._hosts.append(found)

    def _rejected(self, error: MulitaError) -> None:
        self._fail(error)
