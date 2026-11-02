from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from mulita.core import validation
from mulita.core.errors import ValidationError
from mulita.core.platform import RemovableStorage, UsbDrive
from mulita.core.messages import message

_DEVICE = re.compile(r'^[A-Za-z0-9]+$')

_PLACES = {
    'captura': ('Captura', ('.pcap',)),
    'tap': ('TAP', ('.pcap',)),
    'traza': ('Traza', ('.csv',)),
    'ping': ('Ping', ('.csv',)),
    'publica': ('IP pública', ('.csv',)),
    'wifi': ('Info Wi-Fi', ('.csv',)),
    'escaneo': ('Escaneo', ('.csv',)),
    'descubrimiento': ('Descubrimiento', ('.csv',)),
    'tls': ('TLS', ('.csv',)),
    'puerto-switch': ('Puerto de switch', ('.json',)),
}


@dataclass(frozen=True)
class StoredCapture:
    place: str
    place_label: str
    name: str
    size: str
    modified: str


class CaptureFilesService:
    """Capturas .pcap y trazas .csv. No sale de esas carpetas."""

    def __init__(self, directory: PurePosixPath | Path,
                 capture_active=None, tap_active=None,
                 storage: RemovableStorage | None = None):
        self._root = Path(directory)
        self._capture_active = capture_active or (lambda: False)
        self._tap_active = tap_active or (lambda: False)
        self._storage = storage

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
            raise ValidationError(message('nameExists'))
        source.rename(target)
        return target.name

    def copy(self, place: str, name: str, new_name: str) -> str:
        self._guard(place)
        source = self._existing(place, name)
        target = self._destination(place, new_name, self._kept_suffix(place, source))
        if target.exists():
            raise ValidationError(message('nameExists'))
        shutil.copyfile(source, target)
        return target.name

    def delete(self, place: str, name: str) -> None:
        self._guard(place)
        self._existing(place, name).unlink()

    def delete_many(self, items: list[tuple[str, str]]) -> None:
        if not items:
            raise ValidationError(message('noFilesSelected'))
        paths = []
        for place, name in items:
            self._guard(place)
            paths.append(self._existing(place, name))
        for path in paths:
            path.unlink()

    def list_drives(self) -> tuple[UsbDrive, ...]:
        found = self._storage.list_drives() if self._storage is not None else ()
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
            raise ValidationError(message('badDrive'))
        source = self._existing(place, name)
        folder = self._drive_folder(drive_id)
        target = folder / source.name
        if target.exists():
            raise ValidationError(message('usbExists'))
        shutil.copyfile(source, target)
        self._storage.sync()
        return source.name

    def export_many(self, items: list[tuple[str, str]], drive_id: str) -> int:
        if not items:
            raise ValidationError(message('noFilesSelected'))
        if not _DEVICE.fullmatch(drive_id or ''):
            raise ValidationError(message('badDrive'))
        folder = self._drive_folder(drive_id)
        planned: list[tuple[Path, Path]] = []
        names: set[str] = set()
        for place, name in items:
            self._guard(place)
            source = self._existing(place, name)
            if source.name in names:
                raise ValidationError(message('sameFileName'))
            names.add(source.name)
            target = folder / source.name
            if target.exists():
                raise ValidationError(message('usbExists'))
            planned.append((source, target))
        for source, target in planned:
            shutil.copyfile(source, target)
        self._storage.sync()
        return len(planned)

    def _guard(self, place: str) -> None:
        if place == 'captura' and self._capture_active():
            raise ValidationError(message('captureBusy'))
        if place == 'tap' and self._tap_active():
            raise ValidationError(message('tapBusy'))

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
            return self._root / 'internet'
        if place == 'wifi':
            return self._root / 'wifi'
        if place == 'escaneo':
            return self._root / 'escaneo'
        if place == 'descubrimiento':
            return self._root / 'descubrimiento'
        if place == 'tls':
            return self._root / 'tls'
        if place == 'puerto-switch':
            return self._root / 'puerto-switch'
        raise ValidationError(message('badFolder'))

    def _named(self, place: str, name: str, suffix: str = '') -> Path:
        folder = self._folder(place)
        if place == 'ping':
            chosen = suffix if suffix in ('.csv', '.statics.csv') else _ping_suffix(name)
            filename = validation.named_file(validation.ping_basename(name), chosen)
        elif place == 'puerto-switch':
            filename = validation.named_file(name, '.json')
        elif place in ('traza', 'publica', 'wifi', 'escaneo', 'descubrimiento', 'tls'):
            filename = validation.trace_filename(name)
        else:
            filename = validation.capture_filename(name)
        path = folder / filename
        if path.parent.resolve() != folder.resolve():
            raise ValidationError(message('badStoredName'))
        return path

    def _existing(self, place: str, name: str) -> Path:
        path = self._named(place, name)
        if not path.is_file():
            raise ValidationError(message('fileMissing'))
        return path

    def _destination(self, place: str, name: str, suffix: str = '') -> Path:
        return self._named(place, name, suffix)

    def _kept_suffix(self, place: str, source: Path) -> str:
        if place == 'ping':
            return _ping_suffix(source.name)
        return source.suffix.lower()

    def _drive_folder(self, drive_id: str) -> Path:
        if self._storage is None:
            raise ValidationError(message('usbMissing'))
        return self._storage.folder(drive_id)


def _ping_suffix(name: str) -> str:
    if (name or '').lower().endswith('.statics.csv'):
        return '.statics.csv'
    return '.csv'


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
