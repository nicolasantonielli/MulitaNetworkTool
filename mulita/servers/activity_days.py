"""Daily activity files shared by the Qt application and the standalone web server."""
from datetime import date
from pathlib import Path


def day_path(folder: Path, day: str) -> Path:
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError('Fecha inválida')
    path = folder / (day + '.log')
    if folder.is_symlink() or path.is_symlink():
        raise ValueError('Ruta de registro inválida')
    return path


def list_days(folder: Path) -> list[str]:
    if folder.is_symlink():
        raise ValueError('Ruta de registro inválida')
    days = []
    for path in folder.glob('????-??-??.log'):
        try:
            if day_path(folder, path.stem).is_file():
                days.append(path.stem)
        except ValueError:
            continue
    return sorted(days, reverse=True)
