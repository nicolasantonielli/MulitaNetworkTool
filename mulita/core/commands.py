"""Traduce pedidos del negocio a lineas de comando. Siempre listas, nunca shell.

Los comandos viven por dominio (red, Wi-Fi, diagnostico, sistema y servidores).
`CommandFactory` los reune para que los servicios sigan recibiendo un solo objeto.
"""
from __future__ import annotations

from mulita.core.command_base import Argv  # noqa: F401  (se reexporta)
from mulita.core.diagnostic_commands import DiagnosticCommands
from mulita.core.server_commands import ServerCommands
from mulita.core.system_commands import SystemCommands
from mulita.core.wifi_commands import WifiCommands


class CommandFactory(ServerCommands, WifiCommands, DiagnosticCommands, SystemCommands):
    """Todos los comandos externos de Mulita. El constructor viene de `CommandBase`."""
