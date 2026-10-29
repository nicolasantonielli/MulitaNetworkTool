from __future__ import annotations

import json
from typing import Callable

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.errors import MulitaError
from mulita.core.servers import KINDS, RANDOM, ServerLog, kind_by_id
from mulita.presentation.i18n import tr
from mulita.services.servers import suggest_password
from mulita.ui.qt.bridge.base import BridgeContext, Controller

IDLE = 'idle'
STARTING = 'starting'
RUNNING = 'running'


class ServersController(Controller):
    """Varios servidores a la vez. QML ve el estado de todos y el registro del elegido."""

    statesChanged = pyqtSignal()
    rowsChanged = pyqtSignal()
    currentChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext, clock: Callable[[], str] | None = None):
        super().__init__(ctx)
        self._logs = {kind.id: ServerLog(kind, clock) if clock else ServerLog(kind) for kind in KINDS}
        self._states: dict[str, str] = {}
        self._stopping: set[str] = set()
        self._starting: set[str] = set()
        self._early_exits: dict[str, int] = {}
        self._current = ''
        self._password = suggest_password()

    # --- Lo que QML lee -----------------------------------------------------------------

    @pyqtProperty(str, constant=True)
    def catalogJson(self) -> str:
        items = []
        for kind in KINDS:
            item = kind.to_dict()
            for field in item['fields']:
                if field['default'] == RANDOM:
                    field['default'] = self._password
            items.append(item)
        return json.dumps(items)

    @pyqtProperty(str, notify=statesChanged)
    def statesJson(self) -> str:
        return json.dumps(self._states)

    @pyqtProperty(bool, notify=statesChanged)
    def anyRunning(self) -> bool:
        return any(state != IDLE for state in self._states.values())

    @pyqtProperty(str, notify=currentChanged)
    def current(self) -> str:
        return self._current

    @pyqtProperty(str, notify=rowsChanged)
    def rowsJson(self) -> str:
        log = self._logs.get(self._current)
        return json.dumps(log.newest_first() if log else [])

    # --- Acciones -----------------------------------------------------------------------

    @pyqtSlot(str)
    def select(self, kind: str) -> None:
        if kind != self._current and (kind == '' or kind in self._logs):
            self._current = kind
            self.currentChanged.emit()
            self.rowsChanged.emit()

    @pyqtSlot(str, str, result=bool)
    def start(self, kind: str, values_json: str) -> bool:
        if kind not in self._logs or self._states.get(kind, IDLE) != IDLE:
            return False
        try:
            values = json.loads(values_json or '{}')
            if not isinstance(values, dict):
                raise ValueError
        except ValueError:
            values = {}
        self._stopping.discard(kind)
        self._starting.add(kind)
        self._logs[kind].clear()
        self._set_state(kind, STARTING)
        self._notify_rows(kind)
        dispatcher = self._ctx.dispatcher
        servers = self._services.servers
        on_output = dispatcher.wrap(lambda text: self._output(kind, text))
        on_exit = dispatcher.wrap(lambda code: self._exited(kind, code))
        dispatcher.background(
            lambda: servers.start(kind, values, on_output=on_output, on_exit=on_exit),
            lambda _: self._started(kind),
            lambda error: self._rejected(kind, error))
        return True

    @pyqtSlot(str)
    def stop(self, kind: str) -> None:
        if kind not in self._logs or self._states.get(kind, IDLE) == IDLE:
            return
        self._stopping.add(kind)
        # La preparación todavía puede crear recursos o lanzar el proceso.
        # Esperar su respuesta evita limpiar SFTP a mitad de su configuración
        # y mantiene bloqueado un segundo arranque del mismo servidor.
        if kind in self._starting:
            return
        self._services.servers.stop(kind)
        if not self._services.servers.is_running(kind):
            self._set_state(kind, IDLE)

    @pyqtSlot(str)
    def clear(self, kind: str) -> None:
        if kind in self._logs:
            self._logs[kind].clear()
            self._notify_rows(kind)

    @pyqtSlot(str, str)
    def save(self, kind: str, filename: str) -> None:
        if kind not in self._logs:
            return
        try:
            name = self._services.servers.save(kind, list(self._logs[kind].rows), filename)
        except MulitaError as exc:
            self._fail(exc)
            return
        self._ctx.notifier.success(tr(kind_by_id(kind).title), name)

    # --- Respuestas del proceso ---------------------------------------------------------

    def _set_state(self, kind: str, state: str) -> None:
        if state == IDLE:
            changed = self._states.pop(kind, None) is not None
        else:
            changed = self._states.get(kind) != state
            self._states[kind] = state
        if changed:
            self.statesChanged.emit()

    def _notify_rows(self, kind: str) -> None:
        if kind == self._current:
            self.rowsChanged.emit()

    def _started(self, kind: str) -> None:
        self._starting.discard(kind)
        if kind in self._stopping:
            self._services.servers.stop(kind)
            if not self._services.servers.is_running(kind):
                self._exited(kind, self._early_exits.pop(kind, 0))
            return
        if kind in self._early_exits:
            self._exited(kind, self._early_exits.pop(kind))
            return
        # Un proceso que cae al instante avisa su salida antes que esta respuesta.
        if self._states.get(kind) == STARTING and self._services.servers.is_running(kind):
            self._set_state(kind, RUNNING)

    def _rejected(self, kind: str, error: Exception) -> None:
        self._starting.discard(kind)
        self._early_exits.pop(kind, None)
        stopped = kind in self._stopping
        self._stopping.discard(kind)
        self._set_state(kind, IDLE)
        if not stopped:
            self._fail(error)

    def _output(self, kind: str, text: str) -> None:
        if self._logs[kind].feed(text):
            self._notify_rows(kind)

    def _exited(self, kind: str, code: int) -> None:
        if kind in self._starting:
            self._early_exits[kind] = code
            return
        if self._services.servers.is_running(kind):
            return
        if self._logs[kind].flush():
            self._notify_rows(kind)
        stopped = kind in self._stopping
        self._stopping.discard(kind)
        self._set_state(kind, IDLE)
        if code != 0 and not stopped:
            detail = '\n'.join(self._logs[kind].tail) or tr('serverFailed', code=code)
            self._ctx.notifier.error(detail, title=tr(kind_by_id(kind).title))
