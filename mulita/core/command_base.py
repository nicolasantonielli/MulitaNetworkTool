"""Base comun de los generadores de comandos: guarda las rutas de los ejecutables."""
from __future__ import annotations

from pathlib import PurePosixPath

from mulita.core.binaries import Binaries

Argv = list[str]


class CommandBase:
    def __init__(self, binaries: Binaries, server_programs: PurePosixPath | None = None):
        self._bin = binaries
        self._server_programs = server_programs
