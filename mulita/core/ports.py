"""Contratos que la logica de negocio necesita del mundo exterior."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional, Sequence

from mulita.core.models import ClimateReading, CommandResult
from mulita.core.settings import Settings

OutputListener = Callable[[str], None]
ExitListener = Callable[[int], None]


class RunningCommand(ABC):

    @property
    @abstractmethod
    def running(self) -> bool: ...

    @abstractmethod
    def terminate(self) -> None: ...

    @abstractmethod
    def interrupt(self) -> None:
        """Equivale a Ctrl+C: el programa puede imprimir su resumen antes de salir."""


class CommandRunner(ABC):

    @abstractmethod
    def run(self, argv: Sequence[str], timeout: float | None = None,
            input_text: str | None = None) -> CommandResult:
        """Ejecuta y espera el final. Bloquea al que llama.
        `input_text` llega por la entrada estandar: asi un secreto no queda en los argumentos."""

    @abstractmethod
    def start(self, argv: Sequence[str],
              on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None,
              on_error: Optional[OutputListener] = None,
              group: bool = False) -> RunningCommand:
        """Lanza sin esperar. Los callbacks llegan desde otro hilo.
        `on_error` separa stderr. `group` permite detener también los procesos hijos."""


class SettingsStore(ABC):

    @abstractmethod
    def load(self) -> Settings: ...

    @abstractmethod
    def save(self, settings: Settings) -> None: ...


class ClimateSensor(ABC):

    @abstractmethod
    def read(self) -> ClimateReading | None:
        """Lectura cruda, o None si el sensor no respondio."""
