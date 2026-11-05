from __future__ import annotations

from mulita.core.events import EventSource
from mulita.services.operation_events import operation

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from mulita.core import validation
from mulita.core.storage import PLACES, StoragePaths
from mulita.core.errors import ValidationError
from mulita.core.platform import RemovableStorage, UsbDrive
from mulita.core.messages import message

_DEVICE = re.compile(r'^[A-Za-z0-9]+$')

_PLACES = {place.id: (place.label, place.suffixes) for place in PLACES if place.suffixes}


@dataclass(frozen=True)
class StoredCapture:
    place: str
    place_label: str
    name: str
    size: str
    modified: str


class CaptureFilesService(EventSource):
    """Capturas .pcap y trazas .csv. No sale de esas carpetas."""

    def __init__(self, directory: PurePosixPath | Path,
                 capture_active=None, tap_active=None,
                 storage: RemovableStorage | None = None, journal_flush=None):
        self._root = Path(directory)
        self._paths = StoragePaths(self._root)
        self._capture_active = capture_active or (lambda: False)
        self._tap_active = tap_active or (lambda: False)
        self._storage = storage
        self._journal_flush = journal_flush or (lambda _place: None)

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

    @operation('rename', 'name', 'new_name')
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

    @operation('copy', 'name', 'new_name')
    def copy(self, place: str, name: str, new_name: str) -> str:
        self._guard(place)
        source = self._existing(place, name)
        target = self._destination(place, new_name, self._kept_suffix(place, source))
        if target.exists():
            raise ValidationError(message('nameExists'))
        shutil.copyfile(source, target)
        return target.name

    @operation('delete', 'name')
    def delete(self, place: str, name: str) -> None:
        self._guard(place)
        self._existing(place, name).unlink()

    @operation('delete', 'items')
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

    @operation('export')
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

    @operation('export_many', 'items')
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
        self._journal_flush(place)
        if place == 'captura' and self._capture_active():
            raise ValidationError(message('captureBusy'))
        if place == 'tap' and self._tap_active():
            raise ValidationError(message('tapBusy'))

    def _folder(self, place: str) -> Path:
        if place not in _PLACES:
            raise ValidationError(message('badFolder'))
        return self._paths.folder(place)

    def _named(self, place: str, name: str, suffix: str = '') -> Path:
        folder = self._folder(place)
        if place == 'ping':
            chosen = suffix if suffix in ('.csv', '.statics.csv') else _ping_suffix(name)
            filename = validation.named_file(validation.ping_basename(name), chosen)
        elif place in ('puerto-switch', 'actividad', 'bitacora'):
            filename = validation.named_file(name, _PLACES[place][1][0])
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
