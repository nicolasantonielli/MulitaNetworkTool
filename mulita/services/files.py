from __future__ import annotations

import json
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
from mulita.presentation.i18n import tr

_DEVICE = re.compile(r'^[A-Za-z0-9]+$')
_USB_BUS = re.compile(r'usb\d+')
_PARTITION = re.compile(r'p\d+$')
_TRAILING_INDEX = re.compile(r'\d+$')
_MOUNT_ROOT = Path('/mnt/mulita-usb')
_SYSTEM_MOUNTS = {'/', '/boot', '/boot/firmware'}

_PLACES = {
    'captura': ('Captura', ('.pcap',)),
    'tap': ('TAP', ('.pcap',)),
    'traza': ('Traza', ('.csv',)),
    'ping': ('Ping', ('.csv',)),
    'publica': ('IP pública', ('.csv',)),
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
    """Capturas .pcap y trazas .csv. No sale de esas carpetas."""

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
        self._drives = drives

    def list_files(self) -> tuple[StoredCapture, ...]:
        found: list[tuple[float, StoredCapture]] = []
        for place, (label, suffix) in _PLACES.items():
            folder = self._folder(place)
            if not folder.is_dir():
                continue
            allowed = suffix if isinstance(suffix, tuple) else (suffix,)
            for child in folder.iterdir():
                if not child.is_file() or child.suffix.lower() not in allowed:
                    continue
                stat = child.stat()
                found.append((stat.st_mtime, StoredCapture(
                    place=place,
                    place_label=label,
                    name=child.name,
                    size=_size(stat.st_size),
                    modified=datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m %H:%M'),
                )))
        found.sort(key=lambda item: item[0], reverse=True)
        return tuple(item for _when, item in found)

    def rename(self, place: str, name: str, new_name: str) -> str:
        self._guard(place)
        source = self._existing(place, name)
        target = self._destination(place, new_name, self._kept_suffix(place, source))
        if source == target:
            return source.name
        if target.exists():
            raise ValidationError(tr('nameExists'))
        source.rename(target)
        return target.name

    def copy(self, place: str, name: str, new_name: str) -> str:
        self._guard(place)
        source = self._existing(place, name)
        target = self._destination(place, new_name, self._kept_suffix(place, source))
        if target.exists():
            raise ValidationError(tr('nameExists'))
        shutil.copyfile(source, target)
        return target.name

    def delete(self, place: str, name: str) -> None:
        self._guard(place)
        self._existing(place, name).unlink()

    def delete_many(self, items: list[tuple[str, str]]) -> None:
        if not items:
            raise ValidationError(tr('noFilesSelected'))
        paths = []
        for place, name in items:
            self._guard(place)
            paths.append(self._existing(place, name))
        for path in paths:
            path.unlink()

    def list_drives(self) -> tuple[UsbDrive, ...]:
        found = list(self._found_drives())
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
            raise ValidationError(tr('badDrive'))
        source = self._existing(place, name)
        folder = self._drive_folder(drive_id)
        target = folder / source.name
        if target.exists():
            raise ValidationError(tr('usbExists'))
        shutil.copyfile(source, target)
        if hasattr(os, 'sync'):
            os.sync()
        return source.name

    def export_many(self, items: list[tuple[str, str]], drive_id: str) -> int:
        if not items:
            raise ValidationError(tr('noFilesSelected'))
        if not _DEVICE.fullmatch(drive_id or ''):
            raise ValidationError(tr('badDrive'))
        folder = self._drive_folder(drive_id)
        planned: list[tuple[Path, Path]] = []
        names: set[str] = set()
        for place, name in items:
            self._guard(place)
            source = self._existing(place, name)
            if source.name in names:
                raise ValidationError(tr('sameFileName'))
            names.add(source.name)
            target = folder / source.name
            if target.exists():
                raise ValidationError(tr('usbExists'))
            planned.append((source, target))
        for source, target in planned:
            shutil.copyfile(source, target)
        if hasattr(os, 'sync'):
            os.sync()
        return len(planned)

    def _guard(self, place: str) -> None:
        if place == 'captura' and self._capture_active():
            raise ValidationError(tr('captureBusy'))
        if place == 'tap' and self._tap_active():
            raise ValidationError(tr('tapBusy'))

    def _folder(self, place: str) -> Path:
        if place == 'captura':
            return self._root
        if place == 'tap':
            return self._root / 'tap'
        if place == 'traza':
            return self._root / 'trazas'
        if place == 'ping':
            return self._root / 'ping'
        if place == 'publica':
            return self._root / 'publicip'
        raise ValidationError(tr('badFolder'))

    def _named(self, place: str, name: str, suffix: str = '') -> Path:
        folder = self._folder(place)
        if place == 'ping':
            chosen = suffix if suffix in ('.csv', '.statics.csv') else _ping_suffix(name)
            filename = validation.named_file(validation.ping_basename(name), chosen)
        elif place in ('traza', 'publica'):
            filename = validation.trace_filename(name)
        else:
            filename = validation.capture_filename(name)
        path = folder / filename
        if path.parent.resolve() != folder.resolve():
            raise ValidationError(tr('badStoredName'))
        return path

    def _existing(self, place: str, name: str) -> Path:
        path = self._named(place, name)
        if not path.is_file():
            raise ValidationError(tr('fileMissing'))
        return path

    def _destination(self, place: str, name: str, suffix: str = '') -> Path:
        return self._named(place, name, suffix)

    def _kept_suffix(self, place: str, source: Path) -> str:
        if place == 'ping':
            return _ping_suffix(source.name)
        return source.suffix.lower()

    def _found_drives(self) -> tuple[UsbDrive, ...]:
        if self._drives is not None:
            return tuple(self._drives())
        listed = self._from_lsblk()
        if listed:
            return listed
        sysfs = list_usb_drives()
        return sysfs or listed or ()

    def _from_lsblk(self) -> tuple[UsbDrive, ...] | None:
        if self._runner is None or self._commands is None:
            return None
        result = self._runner.run(self._commands.usb_block_devices())
        if not result.ok:
            return None
        return parse_usb_drives(result.text)

    def _drive_folder(self, drive_id: str) -> Path:
        drives = {item.device: item for item in self._found_drives()}
        drive = drives.get(drive_id)
        if drive is None:
            raise ValidationError(tr('usbMissing'))
        mounted = drive.mountpoint or _mount_points().get(f'/dev/{drive_id}', '')
        if mounted:
            folder = Path(mounted)
            if not folder.is_dir():
                raise ValidationError(tr('usbUnusable'))
            return folder
        if self._runner is None or self._commands is None or os.name != 'posix':
            raise ValidationError(tr('usbUnusable'))
        target = _MOUNT_ROOT / drive_id
        target.mkdir(parents=True, exist_ok=True)
        result = self._runner.run(self._commands.mount_partition(drive_id, str(target)))
        if not result.ok:
            raise CommandFailedError('No se pudo preparar el pendrive', result)
        return target


def _ping_suffix(name: str) -> str:
    if (name or '').lower().endswith('.statics.csv'):
        return '.statics.csv'
    return '.csv'


def parse_usb_drives(text: str) -> tuple[UsbDrive, ...]:
    """Discos con transporte usb. No exige que esten montados."""
    try:
        payload = json.loads(text or '')
    except json.JSONDecodeError:
        return ()
    found: list[UsbDrive] = []
    for disk in payload.get('blockdevices') or []:
        if not isinstance(disk, dict) or disk.get('tran') != 'usb' or _holds_system(disk):
            continue
        for node in _filesystem_nodes(disk):
            name = str(node.get('name') or '')
            if not _DEVICE.fullmatch(name):
                continue
            found.append(UsbDrive(name, _node_label(node), _node_mount(node)))
    return tuple(found)


def list_usb_drives(block: Path | None = None, mounts_file: Path | None = None) -> tuple[UsbDrive, ...]:
    """Particiones USB. En la PC de desarrollo no hay /sys/block."""
    block = block or Path('/sys/block')
    if not block.is_dir():
        return ()
    mounts = _mount_points(mounts_file)
    system = _system_disks(mounts)
    found: list[UsbDrive] = []
    for device in block.iterdir():
        if device.name in system or not _usb_disk(device):
            continue
        parts = [child for child in device.iterdir()
                 if child.is_dir() and child.name.startswith(device.name) and _DEVICE.fullmatch(child.name)]
        nodes = parts or ([device] if _DEVICE.fullmatch(device.name) else [])
        for node in nodes:
            dev = f'/dev/{node.name}'
            found.append(UsbDrive(node.name, _volume_label(dev) or 'Pendrive', mounts.get(dev, '')))
    return tuple(found)


def _filesystem_nodes(disk: dict) -> list[dict]:
    children = [child for child in disk.get('children') or [] if isinstance(child, dict)]
    if not children:
        return [disk]
    nodes: list[dict] = []
    for child in children:
        nodes.extend(_filesystem_nodes(child))
    return nodes


def _holds_system(node: dict) -> bool:
    if _node_mount(node) in _SYSTEM_MOUNTS:
        return True
    return any(_holds_system(child) for child in node.get('children') or [] if isinstance(child, dict))


def _node_label(node: dict) -> str:
    label = node.get('label')
    if isinstance(label, str) and label.strip():
        return label.strip()
    return 'Pendrive'


def _node_mount(node: dict) -> str:
    point = node.get('mountpoint')
    if isinstance(point, str) and point:
        return point
    points = node.get('mountpoints') or []
    if isinstance(points, list):
        for item in points:
            if isinstance(item, str) and item:
                return item
    return ''


def _usb_disk(device: Path) -> bool:
    """El pendrive entra como disco SCSI. El bus usb queda en la ruta real, no en subsystem."""
    link = device / 'device'
    try:
        resolved = link.resolve().as_posix()
    except OSError:
        return False
    return any(_USB_BUS.fullmatch(part) for part in PurePosixPath(resolved).parts)


def _system_disks(mounts: dict[str, str]) -> set[str]:
    disks: set[str] = set()
    for device, point in mounts.items():
        if point in _SYSTEM_MOUNTS:
            name = _disk_name(device)
            if name:
                disks.add(name)
    return disks


def _disk_name(device: str) -> str:
    name = PurePosixPath(device).name
    if name == 'root':
        try:
            name = Path('/dev/root').resolve().name
        except OSError:
            return ''
    if _PARTITION.search(name):
        return _PARTITION.sub('', name)
    return _TRAILING_INDEX.sub('', name) or name


def _mount_points(mounts_file: Path | None = None) -> dict[str, str]:
    mounts = mounts_file or Path('/proc/mounts')
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
