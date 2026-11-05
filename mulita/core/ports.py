"""Contratos que la logica de negocio necesita del mundo exterior."""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Callable, Optional, Protocol, Sequence

from mulita.core.models import ClimateReading, CommandResult
from mulita.core.settings import Settings

OutputListener = Callable[[str], None]
ExitListener = Callable[[int], None]


class ExportBundle(Protocol):
    """Stage related exports and publish them together after successful writing.

    The context yields one writable staging path per destination, in order.
    Existing destinations must never be overwritten. A preparation/publication
    failure removes files created by this operation and propagates the error.
    This contract does not promise atomic recovery after power loss.
    """
    def __call__(self, destinations: tuple[Path, ...]) -> AbstractContextManager[tuple[Path, ...]]: ...


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
    def save(self, settings: Settings) -> None:
        """Guarda las preferencias o lanza PersistenceError ante fallas de almacenamiento."""


class ClimateSensor(ABC):

    @abstractmethod
    def read(self) -> ClimateReading | None:
        """Lectura cruda, o None si el sensor no respondio."""
