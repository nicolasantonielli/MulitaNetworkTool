from __future__ import annotations

import csv
import os
from pathlib import Path, PurePosixPath
from typing import Optional

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.models import PingRequest, TraceHop
from mulita.core.parsers import parse_trace
from mulita.presentation.i18n import tr
from mulita.core.ports import CommandRunner, ExitListener, OutputListener
from mulita.services.base import ProcessSession

_CSV_HEADER = ('Salto', 'Direccion', 'Perdida', 'Envios', 'Ultimo', 'Media', 'Mejor', 'Peor', 'Desvio')


class TraceService:

    def __init__(self, runner: CommandRunner, commands: CommandFactory, cycles: int,
                 directory: PurePosixPath | Path = PurePosixPath('/root/capturas/trazas')):
        self._runner = runner
        self._commands = commands
        self._cycles = cycles
        self._directory = Path(directory)

    def trace(self, target: str) -> tuple[TraceHop, ...]:
        result = self._runner.run(self._commands.trace(validation.host(target), self._cycles))
        hops = parse_trace(result.stdout)
        if hops:
            return hops
        if not result.ok:
            detail = _trace_error(result.stderr or result.stdout)
            raise CommandFailedError(detail or tr('traceFailed'), result)
        return ()

    def save(self, hops: tuple[TraceHop, ...], filename: str) -> str:
        if not hops:
            raise ValidationError(tr('noTrace'))
        name = validation.trace_filename(filename)
        self._ensure_directory()
        path = self._directory / name
        if path.parent.resolve() != self._directory.resolve():
            raise ValidationError(tr('badStoredName'))
        if path.exists():
            raise ValidationError(tr('nameExists'))
        try:
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle, lineterminator='\n')
                writer.writerow(_CSV_HEADER)
                for hop in hops:
                    writer.writerow([
                        hop.hop, hop.address, hop.loss, hop.sent,
                        hop.last, hop.average, hop.best, hop.worst, hop.deviation,
                    ])
        except OSError as exc:
            raise CommandFailedError(tr('saveTraceFailed')) from exc
        return name

    def _ensure_directory(self) -> None:
        if os.name != 'posix':
            return
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(tr('traceFolder')) from exc


def _trace_error(text: str) -> str:
    line = next((part.strip() for part in (text or '').splitlines() if part.strip()), '')
    if line.lower().startswith('mtr:'):
        line = line.split(':', 1)[1].strip()
    return line[:180]


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
