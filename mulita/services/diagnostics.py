from __future__ import annotations

from mulita.core.events import EventSource
from mulita.services.operation_events import operation, session

import csv
import os
from pathlib import Path, PurePosixPath
from typing import Optional

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.models import (HostSighting, PingReply, PingRequest, PingSummary,
                                PortFinding, TraceHop)
from mulita.core.parsers import interface_network, parse_port_scan, parse_trace
from mulita.core.messages import message
from mulita.core.ports import CommandRunner, ExitListener, OutputListener, ExportBundle
from mulita.services.base import ProcessSession

_CSV_HEADER = ('hop', 'address', 'loss', 'sent', 'last', 'average', 'best', 'worst', 'deviation')


class TraceService(EventSource):

    def __init__(self, runner: CommandRunner, commands: CommandFactory, cycles: int,
                 directory: PurePosixPath | Path = Path.home() / 'capturas' / 'trazas'):
        self._runner = runner
        self._commands = commands
        self._cycles = cycles
        self._directory = Path(directory)

    @operation('trace', 'target')
    def trace(self, target: str) -> tuple[TraceHop, ...]:
        result = self._runner.run(self._commands.trace(validation.host(target), self._cycles))
        hops = parse_trace(result.stdout)
        if hops:
            return hops
        if not result.ok:
            detail = _trace_error(result.stderr or result.stdout)
            raise CommandFailedError(detail or message('traceFailed'), result)
        return ()

    @operation('export')
    def save(self, hops: tuple[TraceHop, ...], filename: str) -> str:
        if not hops:
            raise ValidationError(message('noTrace'))
        name = validation.trace_filename(filename)
        self._ensure_directory()
        path = self._directory / name
        if path.parent.resolve() != self._directory.resolve():
            raise ValidationError(message('badStoredName'))
        if path.exists():
            raise ValidationError(message('nameExists'))
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
            raise CommandFailedError(message('saveTraceFailed')) from exc
        return name

    def _ensure_directory(self) -> None:
        if os.name != 'posix':
            return
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(message('traceFolder')) from exc


def _ping_status(reply: PingReply) -> str:
    return reply.status if reply.status in ('ok', 'dup') else reply.detail or reply.status or 'error'


def _trace_error(text: str) -> str:
    line = next((part.strip() for part in (text or '').splitlines() if part.strip()), '')
    if line.lower().startswith('mtr:'):
        line = line.split(':', 1)[1].strip()
    return line[:180]


def _write_statics(path: Path, summary: PingSummary) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow([
            'target', 'transmitted', 'received', 'loss',
            'elapsed', 'minimum', 'average',
            'maximum', 'deviation',
        ])
        writer.writerow([
            summary.target, summary.transmitted, summary.received, summary.loss, summary.elapsed,
            summary.minimum, summary.average, summary.maximum, summary.deviation,
        ])


class PingService(ProcessSession):

    def __init__(self, runner: CommandRunner, commands: CommandFactory,
                 directory: PurePosixPath | Path = Path.home() / 'capturas' / 'ping',
                 *, exporter: ExportBundle):
        super().__init__(runner, 'El ping')
        self._commands = commands
        self._directory = Path(directory)
        self._export_bundle = exporter

    @operation('ping_export')
    def save(self, replies: tuple[PingReply, ...], summary: PingSummary | None, filename: str) -> str:
        if not replies and not (summary and summary.ready):
            raise ValidationError(message('noPing'))
        stem = validation.ping_basename(filename)
        base = stem + validation.PING_TABLE_EXTENSION
        statics = stem + validation.PING_STATICS_SUFFIX
        self._ensure_directory()
        folder = self._directory
        table_path = folder / base
        statics_path = folder / statics
        for path in (table_path, statics_path):
            if path.parent.resolve() != folder.resolve():
                raise ValidationError(message('badStoredName'))
            if path.exists():
                raise ValidationError(message('nameExists'))
        try:
            with self._export_bundle((table_path, statics_path)) as staged:
                table_path, statics_path = staged
                with table_path.open('w', encoding='utf-8', newline='') as handle:
                    writer = csv.writer(handle, lineterminator='\n')
                    writer.writerow([
                        'sequence', 'source', 'ttl', 'time', 'status',
                    ])
                    for reply in replies:
                        writer.writerow([
                            reply.seq, reply.source, reply.ttl, reply.time, _ping_status(reply),
                        ])
                _write_statics(statics_path, summary or PingSummary())
        except OSError as exc:
            raise CommandFailedError(message('savePingFailed')) from exc
        if hasattr(os, 'sync'):
            os.sync()
        return base

    def _ensure_directory(self) -> None:
        if os.name != 'posix':
            return
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(message('pingFolder')) from exc

    @session('ping', 'target')
    def start(self, target: str, count: float, interval: float, size: float,
              on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None) -> PingRequest:
        request = validation.ping_request(target, count, interval, size)
        self._launch(self._commands.ping(request), on_output, on_exit)
        return request

    def stop(self) -> None:
        """Interrumpe como Ctrl+C para que ping imprima las estadisticas."""
        self._interrupt()


class PortScanService(EventSource):

    def __init__(self, runner: CommandRunner, commands: CommandFactory,
                 directory: PurePosixPath | Path = Path.home() / 'capturas' / 'escaneo'):
        self._runner = runner
        self._commands = commands
        self._directory = Path(directory)

    @operation('ports', 'arguments')
    def scan(self, arguments: str) -> tuple[PortFinding, ...]:
        result = self._runner.run(self._commands.port_scan(validation.scan_arguments(arguments)))
        found = parse_port_scan(result.stdout)
        if found:
            return found
        if not result.ok:
            detail = (result.text or '').strip()
            raise CommandFailedError(detail or message('scanFailed'), result)
        return ()

    @operation('export')
    def save(self, findings: tuple[PortFinding, ...], filename: str) -> str:
        if not findings:
            raise ValidationError(message('noPorts'))
        name = validation.trace_filename(filename)
        self._ensure_directory()
        path = self._directory / name
        if path.parent.resolve() != self._directory.resolve():
            raise ValidationError(message('badStoredName'))
        if path.exists():
            raise ValidationError(message('nameExists'))
        try:
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle, lineterminator='\n')
                writer.writerow([
                    'host', 'port', 'protocol', 'state', 'service',
                ])
                for item in findings:
                    writer.writerow([item.host, item.port, item.protocol, item.state, item.service])
        except OSError as exc:
            raise CommandFailedError(message('saveScanFailed')) from exc
        if hasattr(os, 'sync'):
            os.sync()
        return name

    def _ensure_directory(self) -> None:
        if os.name != 'posix':
            return
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(message('scanFolder')) from exc


class DiscoveryService(ProcessSession):

    def __init__(self, runner: CommandRunner, commands: CommandFactory,
                 directory: PurePosixPath | Path = Path.home() / 'capturas' / 'descubrimiento'):
        super().__init__(runner, 'El descubrimiento')
        self._commands = commands
        self._directory = Path(directory)

    @session('discovery', 'interface')
    def start(self, interface: str = '', on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None) -> None:
        name = validation.interface_name(interface) if (interface or '').strip() else ''
        network = self._network(name) if name else ''
        self._launch(self._commands.discovery(name, network), on_output, on_exit)

    def _network(self, interface: str) -> str:
        listed = self._runner.run(self._commands.interfaces())
        if not listed.ok:
            raise CommandFailedError(message('speedNoIface'))
        network = interface_network(listed.stdout, interface)
        if not network:
            raise ValidationError(message('discoverNoAddress', interface=interface))
        return network

    @operation('export')
    def save(self, hosts: tuple[HostSighting, ...], filename: str) -> str:
        if not hosts:
            raise ValidationError(message('noHosts'))
        name = validation.trace_filename(filename)
        self._ensure_directory()
        path = self._directory / name
        if path.parent.resolve() != self._directory.resolve():
            raise ValidationError(message('badStoredName'))
        if path.exists():
            raise ValidationError(message('nameExists'))
        try:
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle, lineterminator='\n')
                writer.writerow([
                    'ip', 'mac', 'count', 'vendor',
                ])
                for item in hosts:
                    writer.writerow([item.ip, item.mac, item.count, item.vendor])
        except OSError as exc:
            raise CommandFailedError(message('saveDiscoverFailed')) from exc
        if hasattr(os, 'sync'):
            os.sync()
        return name

    def _ensure_directory(self) -> None:
        if os.name != 'posix':
            return
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(message('discoverFolder')) from exc
