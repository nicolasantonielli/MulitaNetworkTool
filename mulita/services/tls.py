from __future__ import annotations

import csv
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Optional

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import (AlreadyRunningError, CommandFailedError,
                                ValidationError)
from mulita.core.ports import CommandRunner, ExitListener, OutputListener
from mulita.core.tls import (TlsFinding, TlsTarget, mode_flags, parse_report,
                             parse_target, section_label, severity_label, test_label)
from mulita.presentation.i18n import tr
from mulita.services.base import ProcessSession


class TlsService(ProcessSession):
    """Analiza el certificado y la configuracion TLS de un servidor con testssl.sh."""

    def __init__(self, runner: CommandRunner, commands: CommandFactory,
                 directory: PurePosixPath | Path = PurePosixPath('/root/capturas/tls')):
        super().__init__(runner, 'El analisis TLS')
        self._commands = commands
        self._directory = Path(directory)
        self._findings: tuple[TlsFinding, ...] = ()

    @property
    def findings(self) -> tuple[TlsFinding, ...]:
        """Hallazgos del ultimo analisis. Quedan disponibles cuando el proceso termina."""
        return self._findings

    def start(self, target: str, mode: str, on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None) -> TlsTarget:
        parsed = parse_target(target)
        flags = mode_flags(mode)
        if self.is_running:
            raise AlreadyRunningError('El analisis TLS ya esta en ejecucion')
        self._findings = ()
        workdir = Path(tempfile.mkdtemp(prefix='mulita-tls-'))
        report = workdir / 'informe.json'

        def finished(code: int) -> None:
            self._collect(report, workdir)
            if on_exit:
                on_exit(code)

        try:
            self._launch(self._commands.tls_scan(parsed.argument, flags, str(report)),
                         on_output, finished)
        except Exception:
            shutil.rmtree(workdir, ignore_errors=True)
            raise
        return parsed

    def _collect(self, report: Path, workdir: Path) -> None:
        try:
            raw = report.read_text(encoding='utf-8', errors='replace')
        except OSError:
            raw = ''
        self._findings = parse_report(raw)
        shutil.rmtree(workdir, ignore_errors=True)

    def save(self, findings: tuple[TlsFinding, ...], filename: str) -> str:
        if not findings:
            raise ValidationError(tr('noTlsRows'))
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
                writer.writerow([tr('tlsSection'), tr('tlsTest'), tr('tlsSeverity'),
                                 tr('tlsResult'), 'CVE'])
                for item in findings:
                    writer.writerow([section_label(item.section), test_label(item),
                                     severity_label(item.severity), item.text, item.cve])
        except OSError as exc:
            raise CommandFailedError(tr('tlsSaveFailed')) from exc
        if hasattr(os, 'sync'):
            os.sync()
        return name

    def _ensure_directory(self) -> None:
        if os.name != 'posix':
            return
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(tr('tlsFolder')) from exc
