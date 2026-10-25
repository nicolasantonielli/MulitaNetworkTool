from __future__ import annotations

import logging
import os
from typing import Callable

from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError
from mulita.core.models import CommandResult
from mulita.core.ports import CommandRunner

log = logging.getLogger(__name__)

KeyboardListener = Callable[[bool], None]


class MaintenanceService:

    def __init__(self, runner: CommandRunner, commands: CommandFactory,
                 repository_dir: str, service_name: str,
                 update_remote: str = 'origin', update_branch: str = 'v3'):
        self._runner = runner
        self._commands = commands
        self._repository_dir = repository_dir
        self._service_name = service_name
        self._update_remote = update_remote
        self._update_branch = update_branch

    def update(self) -> CommandResult:
        argv = self._commands.update(self._repository_dir, self._update_remote, self._update_branch)
        return self._checked(argv, 'No se pudo actualizar')

    def reset(self) -> CommandResult | None:
        """Con systemd, pide el reinicio del servicio. Sin systemd, None: el proceso se reemplaza."""
        if not os.environ.get('INVOCATION_ID'):
            return None
        return self._checked(self._commands.restart_service(self._service_name), 'No se pudo reiniciar')

    def poweroff(self) -> CommandResult:
        return self._checked(self._commands.poweroff(), 'No se pudo apagar')

    def _checked(self, argv: list[str], message: str) -> CommandResult:
        result = self._runner.run(argv)
        if not result.ok:
            raise CommandFailedError(f'{message}: {result.text}', result)
        return result


class KeyboardService:
    """Un solo teclado en pantalla compartido por todas las barras superiores."""

    def __init__(self, runner: CommandRunner, commands: CommandFactory):
        self._runner = runner
        self._commands = commands
        self._visible = False
        self._listeners: list[KeyboardListener] = []

    @property
    def visible(self) -> bool:
        return self._visible

    def subscribe(self, listener: KeyboardListener) -> None:
        self._listeners.append(listener)

    def toggle(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()

    def show(self) -> None:
        if self._visible:
            return
        self._visible = True
        self._notify()
        self._runner.start(self._commands.keyboard(), on_exit=self._on_exit)

    def hide(self) -> None:
        """onboard puede haber delegado en una instancia previa, por eso killall."""
        if not self._visible:
            return
        self._visible = False
        self._notify()
        self._runner.start(self._commands.hide_keyboard())

    def _on_exit(self, code: int) -> None:
        if code != 0 and self._visible:
            self._visible = False
            self._notify()

    def _notify(self) -> None:
        for listener in self._listeners:
            listener(self.visible)


class ShareService:

    def share(self, source: str) -> None:
        log.info('Funcion share: %s', source)
