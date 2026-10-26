from __future__ import annotations

import logging
import os
from dataclasses import dataclass
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


@dataclass
class _TapLinks:
    entrante: str
    saliente: str
    mirror: str
    bridge: str = 'br-mulita'


class TapService:
    """Pone el equipo entre la boca del switch y otro dispositivo.

    El trafico pasa de la interfaz entrante a la saliente y se graba.
    Si hay una interfaz mirror, ademas se copia hacia ese puerto.
    """

    def __init__(self, runner: CommandRunner | None = None,
                 commands: CommandFactory | None = None,
                 capture: CaptureService | None = None):
        self._runner = runner
        self._commands = commands
        self._capture = capture
        self._config: TapConfig | None = None
        self._links: _TapLinks | None = None
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
        links = self._links_from(config)
        if self._commands is None or self._runner is None:
            raise CommandFailedError('No se pudo preparar el TAP')
        self._quiet(self._commands.link_delete(links.bridge))
        try:
            self._connect(links)
        except Exception:
            self._disconnect(links)
            raise
        recorded = ''
        if filename.strip():
            if self._capture is None:
                self._disconnect(links)
                raise CommandFailedError('No se pudo preparar la captura del TAP')
            try:
                request = self._capture.start(links.bridge, 'inout', filename, on_output, on_exit)
            except Exception:
                self._disconnect(links)
                raise
            self._recording = True
            recorded = request.filename
        self._links = links
        self._config = TapConfig(links.entrante, links.saliente, links.mirror)
        return recorded

    def stop(self) -> None:
        if self._recording and self._capture is not None:
            self._capture.stop()
            self._recording = False
        if self._links is not None:
            self._disconnect(self._links)
            self._links = None
        self._config = None

    def _links_from(self, config: TapConfig) -> _TapLinks:
        entrante = (config.entrante or '').strip()
        saliente = (config.saliente or '').strip()
        mirror = (config.mirror or '').strip()
        if not entrante:
            raise ValidationError('Elegí la interfaz entrante')
        if not saliente:
            raise ValidationError('Elegí la interfaz saliente')
        if entrante == saliente or entrante == 'lo' or saliente == 'lo' or mirror == 'lo':
            raise ValidationError('Esas interfaces no se pueden usar juntas')
        if mirror and mirror in (entrante, saliente):
            raise ValidationError('La interfaz mirror tiene que ser distinta')
        return _TapLinks(entrante, saliente, mirror)

    def _connect(self, links: _TapLinks) -> None:
        commands = self._commands
        self._checked(commands.link_add_bridge(links.bridge), 'No se pudo crear el puente')
        self._checked(commands.link_prepare_bridge(links.bridge), 'No se pudo preparar el puente')
        self._checked(commands.link_up(links.bridge), 'No se pudo levantar el puente')
        self._checked(commands.link_promisc(links.bridge, True), 'No se pudo abrir el puente')
        for interface in (links.entrante, links.saliente):
            self._checked(commands.link_up(interface), f'No se pudo levantar {interface}')
            self._checked(commands.link_master(interface, links.bridge), f'No se pudo unir {interface}')
            self._checked(commands.link_promisc(interface, True), f'No se pudo abrir {interface}')
        if not links.mirror:
            return
        self._checked(commands.link_up(links.mirror), f'No se pudo levantar {links.mirror}')
        self._checked(commands.link_promisc(links.mirror, True), f'No se pudo abrir {links.mirror}')
        for interface in (links.entrante, links.saliente):
            self._checked(commands.ingress_add(interface), f'No se pudo espejar {interface}')
            self._checked(commands.mirror_traffic(interface, links.mirror), f'No se pudo copiar {interface}')

    def _disconnect(self, links: _TapLinks) -> None:
        if self._commands is None:
            return
        commands = self._commands
        for interface in (links.entrante, links.saliente):
            self._quiet(commands.ingress_delete(interface))
            self._quiet(commands.link_nomaster(interface))
            self._quiet(commands.link_promisc(interface, False))
        if links.mirror:
            self._quiet(commands.link_promisc(links.mirror, False))
        self._quiet(commands.link_promisc(links.bridge, False))
        self._quiet(commands.link_delete(links.bridge))

    def _checked(self, argv: list[str], message: str) -> None:
        result = self._runner.run(argv)
        if not result.ok:
            raise CommandFailedError(f'{message}: {result.text}', result)

    def _quiet(self, argv: list[str]) -> None:
        self._runner.run(argv)
