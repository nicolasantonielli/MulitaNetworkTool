"""Brillo del panel por el backlight del kernel."""
from __future__ import annotations

import logging
from pathlib import Path

from mulita.core.errors import CommandFailedError
from mulita.presentation.i18n import tr

log = logging.getLogger(__name__)


class SysfsBacklight:
    """Escribe `/sys/class/backlight/<panel>/brightness`. El 0 % apagaría la pantalla."""

    def __init__(self, root: Path = Path('/sys/class/backlight')):
        self._root = root

    def available(self) -> bool:
        return self._device() is not None

    def apply(self, percent: int) -> None:
        device = self._device()
        if device is None:
            log.info('no hay backlight para el panel')
            return
        maximum = self._maximum(device)
        level = max(1, round(percent * maximum / 100))
        try:
            (device / 'brightness').write_text(f'{level}\n', encoding='ascii')
        except OSError as exc:
            raise CommandFailedError(tr('brightnessFailed')) from exc

    def _device(self) -> Path | None:
        if not self._root.is_dir():
            return None
        found = []
        for path in sorted(self._root.iterdir()):
            name = path.name.lower()
            if 'kbd' in name or 'keyboard' in name:
                continue
            if (path / 'brightness').is_file():
                found.append(path)
        return found[0] if found else None

    def _maximum(self, device: Path) -> int:
        try:
            maximum = int((device / 'max_brightness').read_text(encoding='ascii').strip())
        except (OSError, ValueError):
            return 255
        return maximum if maximum > 0 else 255
