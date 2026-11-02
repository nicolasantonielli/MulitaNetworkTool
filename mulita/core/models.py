from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


MISSING_COMMAND_CODE = 127
TIMEOUT_CODE = 124


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ''
    stderr: str = ''

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def text(self) -> str:
        """Salida a mostrar: stdout si salio bien, stdout y stderr si fallo."""
        if self.ok:
            return self.stdout
        return '\n'.join(part for part in (self.stdout, self.stderr) if part)


class CaptureDirection(Enum):
    ENTRANTE = 'in'
    SALIENTE = 'out'
    AMBAS = 'inout'

    @property
    def label(self) -> str:
        return _DIRECTION_LABELS[self]


_DIRECTION_LABELS = {
    CaptureDirection.ENTRANTE: 'Entrante',
    CaptureDirection.SALIENTE: 'Saliente',
    CaptureDirection.AMBAS: 'Ambos',
}


@dataclass(frozen=True)
class NetworkInterface:
    name: str
    mac: str | None = None
    addresses: tuple[str, ...] = ()
    cable: bool = False


class AddressMode(Enum):
    DHCP = 'dhcp'
    ESTATICA = 'static'

    @property
    def label(self) -> str:
        return 'DHCP' if self is AddressMode.DHCP else 'Estática'


@dataclass(frozen=True)
class WifiNetwork:
    ssid: str
    signal: int = 0
    security: str = ''
    active: bool = False

    @property
    def secure(self) -> bool:
        return bool(self.security)


@dataclass(frozen=True)
class WifiLink:
    """Estado del enlace para un técnico: dirección y radio del AP asociado."""
    interface: str = ''
    ssid: str = ''
    bssid: str = ''
    security: str = ''
    mode: str = ''
    mac: str = ''
    address: str = ''
    netmask: str = ''
    gateway: str = ''
    dns: str = ''
    ipv6: str = ''
    band: str = ''
    channel: str = ''
    frequency: str = ''
    width: str = ''
    center: str = ''
    signal: str = ''
    noise: str = ''
    snr: str = ''
    mcs_rx: str = ''
    mcs_tx: str = ''
    rate_rx: str = ''
    rate_tx: str = ''
    tx_power: str = ''
    uptime: str = ''
    beacon: str = ''
    dtim: str = ''
    retries: str = ''
    failed: str = ''
    beacon_loss: str = ''
    rx: str = ''
    tx: str = ''

    def facts(self) -> list[tuple[str, str]]:
        rows = (
            ('ssid', self.ssid),
            ('bssid', self.bssid),
            ('security', self.security),
            ('mode', self.mode),
            ('interface', self.interface),
            ('mac', self.mac),
            ('address', self.address),
            ('netmask', self.netmask),
            ('gateway', self.gateway),
            ('dns', self.dns),
            ('ipv6', self.ipv6),
            ('band', self.band),
            ('channel', self.channel),
            ('frequency', self.frequency),
            ('width', self.width),
            ('center', self.center),
            ('signal', self.signal),
            ('noise', self.noise),
            ('snr', self.snr),
            ('rate_rx', self.rate_rx),
            ('rate_tx', self.rate_tx),
            ('mcs_rx', self.mcs_rx),
            ('mcs_tx', self.mcs_tx),
            ('tx_power', self.tx_power),
            ('uptime', self.uptime),
            ('beacon', self.beacon),
            ('dtim', self.dtim),
            ('retries', self.retries),
            ('failed', self.failed),
            ('beacon_loss', self.beacon_loss),
            ('rx', self.rx),
            ('tx', self.tx),
        )
        return [(label, value) for label, value in rows if value]


@dataclass(frozen=True)
class EthernetConfig:
    mode: AddressMode = AddressMode.DHCP
    address: str = ''
    prefix: int = 24
    gateway: str = ''
    dns: str = ''


@dataclass(frozen=True)
class CaptureRequest:
    interface: str
    direction: CaptureDirection
    filename: str


@dataclass(frozen=True)
class Range:
    minimum: float
    maximum: float
    default: float

    def contains(self, value: float) -> bool:
        return self.minimum <= value <= self.maximum


PING_COUNT = Range(0, 20, 4)
PING_INTERVAL = Range(0.1, 2, 1)
PING_SIZE = Range(64, 2048, 64)
ICMP_HEADER_BYTES = 8


@dataclass(frozen=True)
class PingReply:
    seq: int
    source: str
    ttl: str
    time: str
    status: str
    detail: str = ''


@dataclass(frozen=True)
class PingSummary:
    target: str = ''
    transmitted: str = ''
    received: str = ''
    loss: str = ''
    elapsed: str = ''
    minimum: str = ''
    average: str = ''
    maximum: str = ''
    deviation: str = ''

    @property
    def ready(self) -> bool:
        return bool(self.transmitted)


@dataclass(frozen=True)
class PingRequest:
    target: str
    count: int
    interval: float
    size: int

    @property
    def continuous(self) -> bool:
        return self.count == 0

    @property
    def payload_bytes(self) -> int:
        return self.size - ICMP_HEADER_BYTES


@dataclass(frozen=True)
class TapConfig:
    entrante: str
    mirror: str
    saliente: str


@dataclass(frozen=True)
class ClimateReading:
    temperature: float
    humidity: float


@dataclass(frozen=True)
class Calibration:
    temperature_offset: float = 0
    humidity_offset: float = 0

    def apply(self, reading: ClimateReading) -> ClimateReading:
        return ClimateReading(
            temperature=reading.temperature + self.temperature_offset,
            humidity=reading.humidity + self.humidity_offset)


@dataclass(frozen=True)
class HostSighting:
    ip: str
    mac: str
    count: str
    vendor: str


@dataclass(frozen=True)
class PortFinding:
    host: str
    port: str
    protocol: str
    state: str
    service: str


@dataclass(frozen=True)
class TraceHop:
    hop: int
    address: str
    loss: str
    sent: str
    last: str
    average: str
    best: str
    worst: str
    deviation: str


@dataclass(frozen=True)
class SpeedTestResult:
    download_bps: float
    upload_bps: float

    @property
    def download_mbps(self) -> float:
        return self.download_bps / 1_000_000

    @property
    def upload_mbps(self) -> float:
        return self.upload_bps / 1_000_000


@dataclass(frozen=True)
class PublicAddress:
    """Salida a Internet vista desde afuera."""
    ip: str
    version: str = ''
    asn: str = ''
    organization: str = ''
    isp: str = ''
    domain: str = ''
    country: str = ''
    region: str = ''
    city: str = ''
    coordinates: str = ''
    timezone: str = ''

    def facts(self) -> list[tuple[str, str]]:
        rows = (
            ('ip', self.ip),
            ('version', self.version),
            ('asn', self.asn),
            ('organization', self.organization),
            ('isp', self.isp),
            ('domain', self.domain),
            ('country', self.country),
            ('region', self.region),
            ('city', self.city),
            ('coordinates', self.coordinates),
            ('timezone', self.timezone),
        )
        return [(label, value) for label, value in rows if value]
