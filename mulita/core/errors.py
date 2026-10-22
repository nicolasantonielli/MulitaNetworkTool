from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mulita.core.models import CommandResult


class MulitaError(Exception):
    """Error de negocio con un mensaje apto para mostrar en pantalla."""


class ValidationError(MulitaError):
    pass


class AlreadyRunningError(MulitaError):
    pass


class CommandFailedError(MulitaError):

    def __init__(self, message: str, result: CommandResult | None = None):
        super().__init__(message)
        self.result = result
