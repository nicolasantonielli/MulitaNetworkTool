"""Contratos que la logica de negocio necesita del mundo exterior."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional, Sequence

from mulita.core.models import ClimateReading, CommandResult

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
    def run(self, argv: Sequence[str], timeout: float | None = None) -> CommandResult:
        """Ejecuta y espera el final. Bloquea al que llama."""

    @abstractmethod
    def start(self, argv: Sequence[str],
              on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None) -> RunningCommand:
        """Lanza sin esperar. Los callbacks llegan desde otro hilo."""


class ClimateSensor(ABC):

    @abstractmethod
    def read(self) -> ClimateReading | None:
        """Lectura cruda, o None si el sensor no respondio."""
