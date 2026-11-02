"""Capacidades de plataforma utilizadas por los servicios."""
from dataclasses import dataclass
from pathlib import Path
from typing import ContextManager, Protocol


class Backlight(Protocol):
    def available(self) -> bool: ...
    def apply(self, percent: int) -> None: ...


@dataclass(frozen=True)
class ReceivedFrame:
    data: bytes
    vlans: tuple[int, ...] = ()


class PacketReceiver(Protocol):
    def receive(self) -> ReceivedFrame | None:
        """Una trama entrante, o None al vencer la espera o ignorar tráfico saliente."""


class PacketSource(Protocol):
    def open(self, interface: str) -> ContextManager[PacketReceiver]: ...


class LinkReader(Protocol):
    def read(self, interface: str) -> dict: ...


class SwitchReportStore(Protocol):
    def save(self, report: dict) -> Path: ...


@dataclass(frozen=True)
class UsbDrive:
    device: str
    label: str
    mountpoint: str = ''


class RemovableStorage(Protocol):
    def list_drives(self) -> tuple[UsbDrive, ...]: ...
    def folder(self, drive_id: str) -> Path: ...
    def sync(self) -> None: ...
