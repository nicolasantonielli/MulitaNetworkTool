from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mulita.core.models import CommandResult


class MulitaError(Exception):
    """Error de negocio cuyo mensaje estructurado se presenta fuera del dominio."""

    @property
    def message(self):
        return self.args[0] if self.args else ''

    @property
    def code(self) -> str:
        return str(self.message)

    @property
    def parameters(self):
        return getattr(self.message, 'parameters', {})

    def __str__(self) -> str:
        if not self.parameters:
            return str(self.message)
        details = ', '.join(f'{key}={value!r}' for key, value in sorted(self.parameters.items()))
        return f'{self.code} ({details})'


class ValidationError(MulitaError):
    pass


class AlreadyRunningError(MulitaError):
    pass


class CommandFailedError(MulitaError):

    def __init__(self, message: str, result: CommandResult | None = None):
        super().__init__(message)
        self.result = result
