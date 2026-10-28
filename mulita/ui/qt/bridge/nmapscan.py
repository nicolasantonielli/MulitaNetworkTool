"""Escaneo Nmap visto desde QML: perfiles, avance, resultados e historial."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Callable

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.errors import MulitaError, ValidationError
from mulita.core.nmapscan import (Progress, checks_view, compile_scan, open_tcp_ports,
                                  profiles_view, update_progress)
from mulita.presentation.i18n import tr
from mulita.ui.qt.bridge.base import BridgeContext, SessionController


class NmapController(SessionController):
    runChanged = pyqtSignal()
    progressChanged = pyqtSignal()
    hostsChanged = pyqtSignal()
    historyChanged = pyqtSignal()
    profilesChanged = pyqtSignal()
    compareChanged = pyqtSignal()
    filesChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext, clock: Callable[[], str] | None = None):
        super().__init__(ctx, ctx.services.nmap)
        self._clock = clock or (lambda: datetime.now().strftime('%H:%M:%S'))
        self._phase = 'idle'
        self._progress = Progress()
        self._hosts: tuple[dict, ...] = ()
        self._partial = False
        self._command = ''
        self._targets = ''
        self._profile = ''
        self._started = ''
        self._fallback = ''
        self._last_ports = ''
        self._last_payload = ''
        self._stopping = False
        self._compare = {'ready': False}
        self._files: list[dict] = []
        self._version_error = ''

    @pyqtProperty(bool, constant=True)
    def simulated(self) -> bool:
        return os.name == 'nt' or bool(self._ctx.config and self._ctx.config.test_mode)

    @pyqtProperty(str, notify=profilesChanged)
    def profilesJson(self) -> str:
        return json.dumps(profiles_view(self._services.nmap.users()))

    @pyqtProperty(str, constant=True)
    def checksJson(self) -> str:
        return json.dumps(checks_view())

    @pyqtProperty(str, notify=runChanged)
    def phase(self) -> str:
        return 'running' if self._running else self._phase

    @pyqtProperty(str, notify=runChanged)
    def command(self) -> str:
        return self._command

    @pyqtProperty(str, notify=runChanged)
    def targets(self) -> str:
        return self._targets

    @pyqtProperty(str, notify=runChanged)
    def started(self) -> str:
        return self._started

    @pyqtProperty(bool, notify=runChanged)
    def partial(self) -> bool:
        return self._partial

    @pyqtProperty(str, notify=runChanged)
    def fallback(self) -> str:
        return self._fallback

    @pyqtProperty(str, notify=runChanged)
    def version(self) -> str:
        return self._services.nmap.version

    @pyqtProperty(str, notify=runChanged)
    def versionError(self) -> str:
        return self._version_error

    @pyqtProperty(str, notify=runChanged)
    def lastPorts(self) -> str:
        return self._last_ports

    @pyqtProperty(str, notify=progressChanged)
    def progressJson(self) -> str:
        return json.dumps(self._progress.view())

    @pyqtProperty(str, notify=hostsChanged)
    def hostsJson(self) -> str:
        return json.dumps(self._hosts)

    @pyqtProperty(str, notify=hostsChanged)
    def summaryJson(self) -> str:
        ports = [port for host in self._hosts for port in host.get('ports', [])]
        return json.dumps({
            'hosts': len(self._hosts),
            'up': sum(1 for host in self._hosts if host.get('state') == 'up'),
            'open': sum(1 for port in ports if port.get('state') == 'open'),
        })

    @pyqtProperty(str, notify=historyChanged)
    def historyJson(self) -> str:
        return json.dumps(self._services.nmap.history())

    @pyqtProperty(str, notify=compareChanged)
    def compareJson(self) -> str:
        return json.dumps(self._compare)

    @pyqtProperty(str, notify=filesChanged)
    def filesJson(self) -> str:
        return json.dumps(self._files)

    @pyqtSlot(str, result=str)
    def commandPreview(self, payload: str) -> str:
        try:
            compiled = compile_scan(self._options(payload), self._saved(), self._services.nmap.resolve)
        except MulitaError as exc:
            return json.dumps({'ok': False, 'command': '', 'notes': [], 'error': str(exc)})
        except (TypeError, ValueError):
            return json.dumps({'ok': False, 'command': '', 'notes': [], 'error': tr('nmapBadArgs', value='')})
        return json.dumps({'ok': True, 'command': compiled.command, 'notes': compiled.notes, 'error': ''})

    @pyqtSlot()
    def refresh(self) -> None:
        def task() -> str:
            try:
                self._services.nmap.probe()
            except MulitaError as exc:
                return str(exc)
            return ''

        self._ctx.dispatcher.background(task, self._probed, lambda _error: None)

    @pyqtSlot()
    def refreshFiles(self) -> None:
        self._files = self._services.nmap.list_files()
        self.filesChanged.emit()

    @pyqtSlot(str, result=bool)
    def start(self, payload: str) -> bool:
        if self._running or self._phase == 'starting':
            return False
        self._stopping = False
        self._services.nmap.reset_cancel()
        self._fallback = ''
        self._progress = Progress()
        self._hosts = ()
        self._partial = False
        self._command = ''
        self._last_payload = payload
        self._console.clear()
        self._phase = 'starting'
        self.runChanged.emit()
        self.progressChanged.emit()
        self.hostsChanged.emit()
        dispatcher = self._ctx.dispatcher
        dispatcher.background(
            lambda: self._services.nmap.prepare(self._options(payload), self.simulated),
            self._launch, self._rejected)
        return True

    @pyqtSlot(result=bool)
    def repeat(self) -> bool:
        if not self._last_payload:
            return False
        return self.start(self._last_payload)

    @pyqtSlot()
    def stop(self) -> None:
        self._stopping = True
        self._services.nmap.request_cancel()
        super().stop()

    @pyqtSlot(str)
    def openRun(self, run_id: str) -> None:
        if self._running or self._phase == 'starting':
            return
        self._ctx.dispatcher.background(
            lambda: self._services.nmap.load(run_id), self._opened, self._fail)

    @pyqtSlot(str, str)
    def compareRuns(self, first: str, second: str) -> None:
        if not first or not second or first == second:
            self._fail(ValidationError(tr('nmapCompareNeed')))
            return
        self._ctx.dispatcher.background(
            lambda: self._services.nmap.compare(first, second), self._compared, self._fail)

    @pyqtSlot(str)
    def saveProfile(self, payload: str) -> None:
        try:
            data = self._options(payload)
            saved = self._services.nmap.save_user(
                str(data.get('profile') or ''), str(data.get('name') or ''),
                str(data.get('description') or ''), str(data.get('custom') or ''))
        except MulitaError as exc:
            self._fail(exc)
            return
        self.profilesChanged.emit()
        self._ctx.notifier.success(tr('cyberNmap'), saved['name'])

    @pyqtSlot(str)
    def deleteProfile(self, profile_id: str) -> None:
        try:
            self._services.nmap.delete_user(profile_id)
        except MulitaError as exc:
            self._fail(exc)
            return
        self.profilesChanged.emit()

    @pyqtSlot(str)
    def duplicateProfile(self, profile_id: str) -> None:
        try:
            saved = self._services.nmap.duplicate_user(profile_id)
        except MulitaError as exc:
            self._fail(exc)
            return
        self.profilesChanged.emit()
        self._ctx.notifier.success(tr('cyberNmap'), saved['name'])

    def _saved(self) -> dict[str, dict]:
        return {item['id']: item for item in self._services.nmap.users()}

    def _options(self, payload: str) -> dict:
        try:
            data = json.loads(payload or '{}')
        except ValueError as exc:
            raise ValidationError(tr('nmapBadArgs', value=exc)) from exc
        if not isinstance(data, dict):
            raise ValidationError(tr('nmapBadArgs', value=''))
        return data

    def _probed(self, error: str) -> None:
        self._version_error = error
        self.runChanged.emit()

    def _launch(self, prepared) -> None:
        if self._stopping:
            self._services.nmap.discard(prepared)
            self._stopping = False
            self._phase = 'cancelled'
            self.runChanged.emit()
            self.historyChanged.emit()
            return
        compiled = prepared.compiled
        self._command = compiled.command
        self._targets = ' '.join(compiled.display[-compiled.target_count:])
        self._profile = compiled.profile_id
        self._started = self._clock()
        dispatcher = self._ctx.dispatcher
        self._services.nmap.launch(
            prepared, on_output=dispatcher.wrap(self._output), on_exit=dispatcher.wrap(self._exited))
        self._set_running(True)
        self._phase = 'running'
        self.runChanged.emit()

    def _rejected(self, error: Exception) -> None:
        self._phase = 'idle'
        self._set_running(False)
        if not self._stopping:
            self._fail(error)
        self._stopping = False
        self.runChanged.emit()

    def _output(self, text: str) -> None:
        self._console.append(text.replace('\r', ''))
        if update_progress(self._progress, text):
            self.progressChanged.emit()

    def _exited(self, code: int) -> None:
        if self._services.nmap.is_running:
            return
        self._set_running(False)
        outcome = self._services.nmap.outcome
        self._stopping = False
        if outcome is None:
            self._phase = 'error'
            self._fail(ValidationError(tr('nmapFailed', code=code)))
        else:
            self._hosts = outcome.hosts
            self._partial = outcome.partial
            self._phase = outcome.status
            self._last_ports = outcome.open_ports
            if outcome.privilege and outcome.profile_id == 'syn':
                self._fallback = 'tcp-standard'
            if outcome.status == 'error':
                self._ctx.notifier.error(outcome.tail or tr('nmapFailed', code=code), title=tr('cyberNmap'))
        self.hostsChanged.emit()
        self.runChanged.emit()
        self.historyChanged.emit()

    def _opened(self, loaded) -> None:
        meta, hosts = loaded
        self._hosts = tuple(hosts)
        self._command = str(meta.get('command') or '')
        self._targets = str(meta.get('targets') or '')
        self._started = str(meta.get('started') or '')
        self._phase = str(meta.get('status') or 'ok')
        self._partial = bool(meta.get('partial'))
        self._last_ports = open_tcp_ports(self._hosts)
        self.hostsChanged.emit()
        self.runChanged.emit()

    def _compared(self, found: dict) -> None:
        found['note'] = tr('nmapCompareNote')
        found['ready'] = True
        self._compare = found
        self.compareChanged.emit()
