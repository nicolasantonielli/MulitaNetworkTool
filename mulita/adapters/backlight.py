"""Brillo del panel, en el momento, sin reiniciar."""
from __future__ import annotations

import ctypes
import logging
import os
import struct
from pathlib import Path
from typing import Callable, Optional

from mulita.core.errors import CommandFailedError
from mulita.presentation.i18n import tr

log = logging.getLogger(__name__)
_CLOEXEC = getattr(os, 'O_CLOEXEC', 0)

# Mailbox de la Raspberry: Set backlight. El firmware lo aplica al instante.
_SET_BACKLIGHT = 0x0004800F
_MAILBOX_OK = 0x80000000


def _mailbox_ioctl() -> int:
    """_IOWR(100, 0, char *). El tamaño del puntero cambia entre 32 y 64 bits."""
    return 0xC0006400 | (struct.calcsize('P') << 16)


def _hardware_level(percent: int, maximum: int) -> int:
    return max(1, round(percent * maximum / 100))


def _write_sysfs(path: Path, payload: bytes) -> None:
    """El truncado a veces falla en sysfs. Si pasa, se escribe igual el valor nuevo."""
    flags = os.O_WRONLY | _CLOEXEC
    try:
        handle = os.open(path, flags | os.O_TRUNC)
    except OSError:
        handle = os.open(path, flags)
    try:
        os.write(handle, payload)
    finally:
        os.close(handle)


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
        level = _hardware_level(percent, maximum)
        try:
            _write_sysfs(device / 'brightness', str(level).encode('ascii'))
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


class MailboxBacklight:
    """Pide el brillo al firmware por `/dev/vcio`. Sirve con el panel DSI en caliente."""

    def __init__(self, device: str = '/dev/vcio', ioctl: Optional[Callable] = None):
        self._device = device
        self._ioctl = ioctl

    def available(self) -> bool:
        return os.path.exists(self._device)

    def apply(self, percent: int) -> None:
        level = _hardware_level(percent, 255)
        words = (ctypes.c_uint32 * 8)()
        words[0] = 32
        words[2] = _SET_BACKLIGHT
        words[3] = 4
        words[5] = level
        try:
            handle = os.open(self._device, os.O_RDWR | _CLOEXEC)
        except OSError as exc:
            raise CommandFailedError(tr('brightnessFailed')) from exc
        try:
            self._call(handle, words)
        except OSError as exc:
            raise CommandFailedError(tr('brightnessFailed')) from exc
        finally:
            os.close(handle)
        returned = ctypes.c_int32(words[5]).value
        if words[1] != _MAILBOX_OK or returned < 0:
            raise CommandFailedError(tr('brightnessFailed'))

    def _call(self, handle: int, words: ctypes.Array) -> None:
        ioctl = self._ioctl
        if ioctl is None:
            import fcntl
            ioctl = fcntl.ioctl
        ioctl(handle, _mailbox_ioctl(), words, True)


class PanelBacklight:
    """Primero el backlight del kernel. Si no está, el mailbox del firmware."""

    def __init__(self, sysfs: SysfsBacklight | None = None,
                 mailbox: MailboxBacklight | None = None):
        self._sysfs = sysfs or SysfsBacklight()
        self._mailbox = mailbox or MailboxBacklight()

    def available(self) -> bool:
        return self._sysfs.available() or self._mailbox.available()

    def apply(self, percent: int) -> None:
        if self._sysfs.available():
            self._sysfs.apply(percent)
            return
        if self._mailbox.available():
            self._mailbox.apply(percent)
            return
        log.info('no hay backlight para el panel')
