"""Immutable diagnostic contracts, independent of service implementation details."""
from dataclasses import dataclass, fields, is_dataclass
from functools import lru_cache
from types import UnionType
from typing import TypeAlias, get_type_hints, get_origin, get_args

from mulita.core.models import (PingSummary, TraceHop, PortFinding, ClimateReading,
                                SpeedTestResult, WifiLink)


@dataclass(frozen=True)
class ExportItem:
    place: str
    name: str


@dataclass(frozen=True)
class OperationParameters:
    detail: str = ''
    target: str = ''
    interface: str = ''
    kind: str = ''
    test: str = ''
    place: str = ''
    items: tuple[ExportItem, ...] = ()
    exit_code: int | None = None
    stopped: bool = False


@dataclass(frozen=True)
class PingReport:
    summary: PingSummary
    replies: int


@dataclass(frozen=True)
class TraceReport:
    hops: tuple[TraceHop, ...]


@dataclass(frozen=True)
class PortsReport:
    findings: tuple[PortFinding, ...]


@dataclass(frozen=True)
class HostReport:
    ip: str
    mac: str


@dataclass(frozen=True)
class DiscoveryReport:
    hosts: tuple[HostReport, ...]


@dataclass(frozen=True)
class WakeReport:
    mac: str
    target: str
    port: str


@dataclass(frozen=True)
class ClimateReport:
    reading: ClimateReading | None


@dataclass(frozen=True)
class PublicIpReport:
    ip: str


@dataclass(frozen=True)
class VendorReport:
    name: str


@dataclass(frozen=True)
class TapReport:
    filename: str


@dataclass(frozen=True)
class SeverityCount:
    severity: str
    count: int


@dataclass(frozen=True)
class TlsReport:
    counts: tuple[SeverityCount, ...]


@dataclass(frozen=True)
class NmapReport:
    status: str
    hosts: tuple[str, ...]
    open_ports: str


@dataclass(frozen=True)
class NeighborReport:
    name: str
    port: str


@dataclass(frozen=True)
class SwitchReport:
    interface: str
    cancelled: bool
    frames: int
    neighbors: tuple[NeighborReport, ...]


@dataclass(frozen=True)
class ExportReport:
    names: tuple[str, ...]


OperationResult: TypeAlias = (PingReport | TraceReport | PortsReport | DiscoveryReport |
    WakeReport | ClimateReport | SpeedTestResult | PublicIpReport | VendorReport |
    TapReport | TlsReport | NmapReport | SwitchReport | WifiLink | ExportReport)

RESULT_TYPES = {
    'ping': PingReport, 'trace': TraceReport, 'ports': PortsReport,
    'discovery': DiscoveryReport, 'wol': WakeReport, 'climate': ClimateReport,
    'speed': SpeedTestResult, 'public_ip': PublicIpReport, 'vendor': VendorReport,
    'tap': TapReport, 'tls': TlsReport, 'nmap': NmapReport, 'switch': SwitchReport,
    'wifi_info': WifiLink, 'export': ExportReport, 'ping_export': ExportReport,
    'web_export': ExportReport, 'export_many': ExportReport,
}


@lru_cache(maxsize=None)
def _hints(cls):
    return get_type_hints(cls)


def validate_payload(value):
    """Fail at publication, including malformed nested results, not in a renderer."""
    if not is_dataclass(value):
        raise TypeError('An event payload must be a typed dataclass')
    for field in fields(value):
        member = getattr(value, field.name)
        if not _matches(member, _hints(type(value))[field.name]):
            raise TypeError(f'Invalid event field {type(value).__name__}.{field.name}')


def _matches(value, expected):
    origin = get_origin(expected)
    if origin is UnionType:
        return any(_matches(value, item) for item in get_args(expected))
    if origin is tuple:
        args = get_args(expected)
        return isinstance(value, tuple) and all(_matches(item, args[0]) for item in value)
    if expected is float:
        return type(value) in (int, float)
    if not isinstance(value, expected) or (expected is int and type(value) is bool):
        return False
    if is_dataclass(value):
        validate_payload(value)
    return True
