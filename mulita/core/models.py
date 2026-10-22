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
class SpeedTestResult:
    download_bps: float
    upload_bps: float

    @property
    def download_mbps(self) -> float:
        return self.download_bps / 1_000_000

    @property
    def upload_mbps(self) -> float:
        return self.upload_bps / 1_000_000
