"""Filesystem helpers used inside the shared journal repository's transactions."""
from datetime import date, datetime
from pathlib import Path


def day_path(folder: Path, day: str, suffix: str = '.log') -> Path:
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError('Fecha inválida')
    path = folder / (day + suffix)
    if folder.is_symlink() or path.is_symlink():
        raise ValueError('Ruta de registro inválida')
    return path


def list_days(folder: Path, suffix: str = '.log') -> list[str]:
    if folder.is_symlink():
        raise ValueError('Ruta de registro inválida')
    days = []
    for path in folder.glob('????-??-??' + suffix):
        try:
            if day_path(folder, path.stem, suffix).is_file():
                days.append(path.stem)
        except ValueError:
            continue
    return sorted(days, reverse=True)


def append_entry(folder: Path, now: datetime, suffix: str, line: str):
    folder.mkdir(parents=True, exist_ok=True)
    with day_path(folder, now.date().isoformat(), suffix).open('a', encoding='utf-8') as stream:
        stream.write(line + '\n')
