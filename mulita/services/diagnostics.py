from __future__ import annotations

from typing import Optional

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.models import PingRequest
from mulita.core.ports import CommandRunner, ExitListener, OutputListener
from mulita.services.base import ProcessSession


class TraceService:

    def __init__(self, runner: CommandRunner, commands: CommandFactory, cycles: int):
        self._runner = runner
        self._commands = commands
        self._cycles = cycles

    def trace(self, target: str) -> str:
        return self._runner.run(self._commands.trace(validation.host(target), self._cycles)).text


class PingService(ProcessSession):

    def __init__(self, runner: CommandRunner, commands: CommandFactory):
        super().__init__(runner, 'El ping')
        self._commands = commands

    def start(self, target: str, count: float, interval: float, size: float,
              on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None) -> PingRequest:
        request = validation.ping_request(target, count, interval, size)
        self._launch(self._commands.ping(request), on_output, on_exit)
        return request

    def stop(self) -> None:
        """Interrumpe como Ctrl+C para que ping imprima las estadisticas."""
        self._interrupt()


class PortScanService:

    def __init__(self, runner: CommandRunner, commands: CommandFactory):
        self._runner = runner
        self._commands = commands

    def scan(self, arguments: str) -> str:
        return self._runner.run(self._commands.port_scan(validation.scan_arguments(arguments))).text


class DiscoveryService(ProcessSession):

    def __init__(self, runner: CommandRunner, commands: CommandFactory):
        super().__init__(runner, 'El descubrimiento')
        self._commands = commands

    def start(self, on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None) -> None:
        self._launch(self._commands.discovery(), on_output, on_exit)
