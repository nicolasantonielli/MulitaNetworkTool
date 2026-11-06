"""Translate service return values into stable event contracts at the boundary."""
from collections import Counter
from pathlib import PurePath
import logging
from datetime import datetime
from typing import Any, Mapping

from mulita.core.events import OperationEvent, EventSource, EventPhase
from mulita.core.event_payloads import (OperationParameters, ExportItem, ExportReport,
    PingReport, TraceReport, PortsReport, HostReport, DiscoveryReport, WakeReport,
    ClimateReport, PublicIpReport, VendorReport, TapReport, TlsReport, SeverityCount,
    NmapReport, NeighborReport, SwitchReport, OperationResult)


def make_event(action: str, phase: EventPhase, parameters: Mapping[str, Any], result: Any = None,
               operation_id: str | None = None, occurred_at: datetime | None = None) -> OperationEvent:
    """Raw dictionaries end here; consumers only receive immutable typed facts."""
    p = parameters
    detail = str(next((p[key] for key in ('target', 'interface', 'ssid', 'mac', 'name') if key in p), ''))
    if action == 'tap' and 'config' in p:
        detail = f'{p["config"].entrante} → {p["config"].saliente}'
    items = tuple(ExportItem(place, name) for place, name in p.get('items', ()))
    if items:
        detail = ', '.join(item.name for item in items)
    facts = OperationParameters(detail=detail, target=p.get('target', ''),
        interface=p.get('interface', ''), kind=p.get('kind', ''), test=p.get('test') or '',
        place=p.get('place', ''), items=items, exit_code=p.get('exit_code'), stopped=p.get('stopped', False))
    value = _result(action, result, items) if phase == 'completed' else None
    extra = {}
    if operation_id is not None:
        extra['operation_id'] = operation_id
    if occurred_at is not None:
        extra['occurred_at'] = occurred_at
    return OperationEvent(action, phase, facts, value, **extra)


def publish_event(source: EventSource, action: str, phase: EventPhase, parameters: Mapping[str, Any],
                  result: Any = None, operation_id: str | None = None) -> None:
    # A contract mismatch must be visible, but cannot fail a diagnostic or its callback.
    try:
        source.emit_event(make_event(action, phase, parameters, result, operation_id))
    except Exception:
        logging.getLogger(__name__).exception('Invalid diagnostic event contract: %s/%s', action, phase)


_EXPORT_ACTIONS = ('export', 'web_export', 'ping_export', 'export_many')


def _export(action: str, value: Any, items: tuple[ExportItem, ...]) -> ExportReport:
    names = tuple(item.name for item in items) if action == 'export_many' else (PurePath(value).name,)
    if action == 'ping_export':
        names += (names[0][:-4] + '.statics.csv',)
    return ExportReport(names)


def _tls(value: Any) -> TlsReport:
    counts = Counter(finding.severity for finding in value)
    return TlsReport(tuple(SeverityCount(severity, count) for severity, count in counts.items()))


def _nmap(value: Any) -> NmapReport:
    if not value:
        return NmapReport('', (), '')
    return NmapReport(value.status, tuple(h['ip'] for h in value.hosts if h.get('ip')), value.open_ports)


def _switch(value: Any) -> SwitchReport:
    neighbors = tuple(NeighborReport(row.get('name') or row.get('chassis') or '', row.get('port') or '')
                      for row in value.get('neighbors', ()))
    return SwitchReport(value.get('interface', ''), value['cancelled'], value.get('frames', 0), neighbors)


# Accion -> como se convierte lo que devolvio el servicio en un resultado tipado.
_RESULTS = {
    'ping': lambda value: PingReport(value['summary'], value['replies']),
    'trace': lambda value: TraceReport(tuple(value)),
    'ports': lambda value: PortsReport(tuple(value)),
    'discovery': lambda value: DiscoveryReport(tuple(HostReport(host.ip, host.mac) for host in value)),
    'wol': lambda value: WakeReport(value.mac, value.target, value.port),
    'climate': ClimateReport,
    'speed': lambda value: value,
    'wifi_info': lambda value: value,
    'public_ip': lambda value: PublicIpReport(value.ip),
    'vendor': lambda value: VendorReport(value or ''),
    'tap': lambda value: TapReport(value or ''),
    'tls': _tls,
    'nmap': _nmap,
    'switch': _switch,
}


def _result(action: str, value: Any, items: tuple[ExportItem, ...]) -> OperationResult | None:
    if action in _EXPORT_ACTIONS:
        return _export(action, value, items)
    # System operations and capture completion need no diagnostic payload.
    build = _RESULTS.get(action)
    return build(value) if build else None
