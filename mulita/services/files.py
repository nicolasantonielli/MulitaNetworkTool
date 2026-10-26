from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from mulita.core import validation
from mulita.core.errors import ValidationError

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


class CaptureFilesService:
    """Archivos .pcap de la captura y del TAP. No sale de esas carpetas."""

    def __init__(self, directory: PurePosixPath | Path,
                 capture_active=None, tap_active=None):
        self._root = Path(directory)
        self._capture_active = capture_active or (lambda: False)
        self._tap_active = tap_active or (lambda: False)

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
