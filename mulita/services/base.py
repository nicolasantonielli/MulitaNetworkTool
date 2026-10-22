from __future__ import annotations

from typing import Optional, Sequence

from mulita.core.errors import AlreadyRunningError
from mulita.core.ports import (CommandRunner, ExitListener, OutputListener,
                               RunningCommand)


class ProcessSession:
    """Un proceso largo a la vez, con arranque y parada."""

    def __init__(self, runner: CommandRunner, name: str):
        self._runner = runner
        self._name = name
        self._handle: RunningCommand | None = None

    @property
    def is_running(self) -> bool:
        return self._handle is not None and self._handle.running

    def _launch(self, argv: Sequence[str],
                on_output: Optional[OutputListener] = None,
                on_exit: Optional[ExitListener] = None) -> None:
        if self.is_running:
            raise AlreadyRunningError(f'{self._name} ya esta en ejecucion')
        self._handle = self._runner.start(argv, on_output=on_output, on_exit=on_exit)

    def stop(self) -> None:
        if self.is_running:
            self._handle.terminate()

    def _interrupt(self) -> None:
        if self.is_running:
            self._handle.interrupt()
