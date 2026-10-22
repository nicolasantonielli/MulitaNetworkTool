from __future__ import annotations

import logging
from pathlib import PurePosixPath
from typing import Optional

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError
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
        self._launch(self._commands.capture(request, self._directory), on_output, on_exit)
        return request


class TapService:
    """Guarda la configuracion del TAP. El puente entre interfaces aun no existe."""

    def __init__(self):
        self._config: TapConfig | None = None

    @property
    def is_running(self) -> bool:
        return self._config is not None

    @property
    def config(self) -> TapConfig | None:
        return self._config

    def start(self, config: TapConfig) -> None:
        self._config = config

    def stop(self) -> None:
        self._config = None
