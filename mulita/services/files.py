from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.ports import CommandRunner

_DEVICE = re.compile(r'^[A-Za-z0-9]+$')
_MOUNT_ROOT = Path('/mnt/mulita-usb')

_PLACES = {
    'captura': 'Captura',
    'tap': 'TAP',
}


@dataclass(frozen=True)
class StoredCapture:
    place: str
    place_label: str
    name: str
    size: str
    modified: str


@dataclass(frozen=True)
class UsbDrive:
    device: str
    label: str
    mountpoint: str = ''


class CaptureFilesService:
    """Archivos .pcap de la captura y del TAP. No sale de esas carpetas."""

    def __init__(self, directory: PurePosixPath | Path,
                 capture_active=None, tap_active=None,
                 runner: CommandRunner | None = None,
                 commands: CommandFactory | None = None,
                 drives=None):
        self._root = Path(directory)
        self._capture_active = capture_active or (lambda: False)
        self._tap_active = tap_active or (lambda: False)
        self._runner = runner
        self._commands = commands
        self._drives = drives or list_usb_drives

    def list_files(self) -> tuple[StoredCapture, ...]:
        found: list[tuple[float, StoredCapture]] = []
        for place in _PLACES:
            folder = self._folder(place)
            if not folder.is_dir():
                continue
            for child in folder.iterdir():
                if not child.is_file() or child.suffix.lower() != '.pcap':
                    continue
                stat = child.stat()
                found.append((stat.st_mtime, StoredCapture(
                    place=place,
                    place_label=_PLACES[place],
                    name=child.name,
                    size=_size(stat.st_size),
                    modified=datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m %H:%M'),
                )))
        found.sort(key=lambda item: item[0], reverse=True)
        return tuple(item for _when, item in found)

    def rename(self, place: str, name: str, new_name: str) -> str:
        self._guard(place)
        source = self._existing(place, name)
        target = self._destination(place, new_name)
        if source == target:
            return source.name
        if target.exists():
            raise ValidationError('Ya existe un archivo con ese nombre')
        source.rename(target)
        return target.name

    def copy(self, place: str, name: str, new_name: str) -> str:
        self._guard(place)
        source = self._existing(place, name)
        target = self._destination(place, new_name)
        if target.exists():
            raise ValidationError('Ya existe un archivo con ese nombre')
        shutil.copyfile(source, target)
        return target.name

    def delete(self, place: str, name: str) -> None:
        self._guard(place)
        self._existing(place, name).unlink()

    def list_drives(self) -> tuple[UsbDrive, ...]:
        found = list(self._drives())
        labels: dict[str, int] = {}
        named: list[UsbDrive] = []
        for drive in found:
            count = labels.get(drive.label, 0) + 1
            labels[drive.label] = count
            label = drive.label if count == 1 else f'{drive.label} {count}'
            named.append(UsbDrive(drive.device, label, drive.mountpoint))
        return tuple(named)

    def export(self, place: str, name: str, drive_id: str) -> str:
        self._guard(place)
        if not _DEVICE.fullmatch(drive_id or ''):
            raise ValidationError('Pendrive invalido')
        source = self._existing(place, name)
        folder = self._drive_folder(drive_id)
        target = folder / source.name
        if target.exists():
            raise ValidationError('En el pendrive ya existe ese archivo')
        shutil.copyfile(source, target)
        if hasattr(os, 'sync'):
            os.sync()
        return source.name

    def _guard(self, place: str) -> None:
        if place == 'captura' and self._capture_active():
            raise ValidationError('Hay una captura en curso')
        if place == 'tap' and self._tap_active():
            raise ValidationError('Hay un TAP en curso')

    def _folder(self, place: str) -> Path:
        if place == 'captura':
            return self._root
        if place == 'tap':
            return self._root / 'tap'
        raise ValidationError('Carpeta invalida')

    def _named(self, place: str, name: str) -> Path:
        folder = self._folder(place)
        filename = validation.capture_filename(name)
        path = folder / filename
        if path.parent.resolve() != folder.resolve():
            raise ValidationError('Nombre de archivo invalido')
        return path

    def _existing(self, place: str, name: str) -> Path:
        path = self._named(place, name)
        if not path.is_file():
            raise ValidationError('No se encontro el archivo')
        return path

    def _destination(self, place: str, name: str) -> Path:
        return self._named(place, name)

    def _drive_folder(self, drive_id: str) -> Path:
        drives = {item.device: item for item in self._drives()}
        drive = drives.get(drive_id)
        if drive is None:
            raise ValidationError('No se encontro el pendrive')
        if drive.mountpoint:
            folder = Path(drive.mountpoint)
            if not folder.is_dir():
                raise ValidationError('No se pudo usar el pendrive')
            return folder
        if self._runner is None or self._commands is None or os.name != 'posix':
            raise ValidationError('No se pudo usar el pendrive')
        target = _MOUNT_ROOT / drive_id
        target.mkdir(parents=True, exist_ok=True)
        result = self._runner.run(self._commands.mount_partition(drive_id, str(target)))
        if not result.ok:
            raise CommandFailedError('No se pudo preparar el pendrive', result)
        return target


def list_usb_drives() -> tuple[UsbDrive, ...]:
    """Particiones USB extraibles. En la PC de desarrollo no hay /sys/block."""
    block = Path('/sys/block')
    if not block.is_dir():
        return ()
    mounts = _mount_points()
    found: list[UsbDrive] = []
    for device in block.iterdir():
        if not _usb_disk(device):
            continue
        parts = [child for child in device.iterdir()
                 if child.is_dir() and child.name.startswith(device.name) and _DEVICE.fullmatch(child.name)]
        nodes = parts or ([device] if _DEVICE.fullmatch(device.name) else [])
        for node in nodes:
            dev = f'/dev/{node.name}'
            found.append(UsbDrive(node.name, _volume_label(dev) or 'Pendrive', mounts.get(dev, '')))
    return tuple(found)


def _usb_disk(device: Path) -> bool:
    removable = device / 'removable'
    subsystem = device / 'device' / 'subsystem'
    try:
        if not removable.is_file() or removable.read_text(encoding='utf-8').strip() != '1':
            return False
        return subsystem.resolve().name == 'usb'
    except OSError:
        return False


def _mount_points() -> dict[str, str]:
    mounts = Path('/proc/mounts')
    if not mounts.is_file():
        return {}
    found = {}
    for line in mounts.read_text(encoding='utf-8', errors='replace').splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith('/dev/'):
            found[parts[0]] = parts[1].replace('\\040', ' ')
    return found


def _volume_label(device: str) -> str:
    folder = Path('/dev/disk/by-label')
    if not folder.is_dir():
        return ''
    try:
        target = Path(device).resolve()
    except OSError:
        return ''
    for entry in folder.iterdir():
        try:
            if entry.resolve() == target:
                return entry.name.replace('\\x20', ' ')
        except OSError:
            continue
    return ''


def _size(amount: int) -> str:
    value = float(amount)
    for unit in ('B', 'KiB', 'MiB', 'GiB'):
        if value < 1024 or unit == 'GiB':
            if unit == 'B':
                return f'{int(value)} B'
            text = f'{value:.1f}'.rstrip('0').rstrip('.')
            return f'{text} {unit}'
        value /= 1024
    return f'{amount} B'
