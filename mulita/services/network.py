from __future__ import annotations

import logging
import os
from pathlib import Path, PurePosixPath
from typing import Optional

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import AlreadyRunningError, CommandFailedError, ValidationError
from mulita.core.models import CaptureRequest, NetworkInterface, TapConfig
from mulita.core.parsers import parse_interfaces
from mulita.core.ports import CommandRunner, ExitListener, OutputListener
from mulita.services.base import ProcessSession

log = logging.getLogger(__name__)


class InterfaceService:

    def __init__(self, runner: CommandRunner, commands: CommandFactory):
        self._runner = runner
        self._commands = commands

    def list_interfaces(self) -> list[NetworkInterface]:
        result = self._runner.run(self._commands.interfaces())
        if not result.ok:
            raise CommandFailedError(f'No se pudieron leer las interfaces: {result.text}', result)
        return parse_interfaces(result.stdout)

    def names(self) -> list[str]:
        """Nunca falla: sin interfaces la pantalla queda vacia en vez de cerrarse."""
        try:
            return [interface.name for interface in self.list_interfaces()]
        except CommandFailedError as exc:
            log.warning('%s', exc)
            return []

    def addresses(self) -> list[str]:
        return [address for interface in self.list_interfaces() for address in interface.addresses]

    def macs(self) -> list[str]:
        return [interface.mac for interface in self.list_interfaces() if interface.mac]


class CaptureService(ProcessSession):

    def __init__(self, runner: CommandRunner, commands: CommandFactory, directory: PurePosixPath):
        super().__init__(runner, 'La captura')
        self._commands = commands
        self._directory = directory

    def start(self, interface: str, direction: str, filename: str,
              on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None) -> CaptureRequest:
        request = validation.capture_request(interface, direction, filename)
        self._ensure_directory()
        self._launch(self._commands.capture(request, self._directory), on_output, on_exit)
        return request

    def _ensure_directory(self) -> None:
        """La Pi no tiene Escritorio. La carpeta se crea en el home de root."""
        if os.name != 'posix':
            return
        try:
            Path(self._directory).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError('No se pudo preparar la carpeta de capturas') from exc


class TapService:
    """Guarda las interfaces del TAP. El puente todavía no existe.

    Si hay un nombre de archivo, graba el puerto mirror en la carpeta del TAP.
    """

    def __init__(self, capture: CaptureService | None = None):
        self._config: TapConfig | None = None
        self._capture = capture
        self._recording = False

    @property
    def is_running(self) -> bool:
        return self._config is not None

    @property
    def config(self) -> TapConfig | None:
        return self._config

    def start(self, config: TapConfig, filename: str = '',
              on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None) -> str:
        if self.is_running:
            raise AlreadyRunningError('El TAP ya esta en ejecucion')
        recorded = ''
        if filename.strip():
            if not (config.mirror or '').strip():
                raise ValidationError('Elegí la interfaz mirror para capturar')
            if self._capture is None:
                raise CommandFailedError('No se pudo preparar la captura del TAP')
            request = self._capture.start(config.mirror, 'inout', filename, on_output, on_exit)
            self._recording = True
            recorded = request.filename
        self._config = config
        return recorded

    def stop(self) -> None:
        if self._recording and self._capture is not None:
            self._capture.stop()
            self._recording = False
        self._config = None
