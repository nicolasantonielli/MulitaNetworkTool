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
    CaptureDirection.AMBAS: 'Entrante y Saliente',
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
            ('Red', self.ssid),
            ('BSSID', self.bssid),
            ('Seguridad', self.security),
            ('Modo', self.mode),
            ('Interfaz', self.interface),
            ('MAC', self.mac),
            ('Dirección IP', self.address),
            ('Máscara', self.netmask),
            ('Puerta de enlace', self.gateway),
            ('DNS', self.dns),
            ('IPv6', self.ipv6),
            ('Banda', self.band),
            ('Canal', self.channel),
            ('Frecuencia', self.frequency),
            ('Ancho de canal', self.width),
            ('Frecuencia central', self.center),
            ('Señal', self.signal),
            ('Ruido', self.noise),
            ('SNR', self.snr),
            ('Velocidad de bajada', self.rate_rx),
            ('Velocidad de subida', self.rate_tx),
            ('MCS de bajada', self.mcs_rx),
            ('MCS de subida', self.mcs_tx),
            ('Potencia de transmisión', self.tx_power),
            ('Tiempo en línea', self.uptime),
            ('Beacon', self.beacon),
            ('DTIM', self.dtim),
            ('Reintentos de envío', self.retries),
            ('Envíos fallidos', self.failed),
            ('Beacons perdidos', self.beacon_loss),
            ('Recibido', self.rx),
            ('Enviado', self.tx),
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
