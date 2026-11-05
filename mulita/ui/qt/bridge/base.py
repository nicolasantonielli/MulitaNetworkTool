"""Piezas comunes de los controladores que QML ve como objetos de contexto."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, TYPE_CHECKING
import json
from pathlib import PurePath

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from mulita.config import AppConfig
from mulita.core.errors import MulitaError
from mulita.presentation.dispatcher import UiDispatcher
from mulita.presentation.i18n import Translator
if TYPE_CHECKING:
    from mulita.services.settings import SettingsService


class Notifier(QObject):
    technicalNote = pyqtSignal(str)
    activityRecorded = pyqtSignal(str, str, str)
    notified = pyqtSignal(str, str, str, arguments=['kind', 'title', 'message'])

    def info(self, title: str, message: str) -> None:
        self.notified.emit('info', title, message)

    def success(self, title: str, message: str) -> None:
        self.notified.emit('success', title, message)

    def error(self, message: str, title: str = 'Error') -> None:
        self.notified.emit('error', title, message)


class Console(QObject):
    """Salida de texto incremental: QML agrega lineas sin reemplazar todo el contenido."""
    appended = pyqtSignal(str, arguments=['text'])
    cleared = pyqtSignal()

    @pyqtSlot()
    def clear(self) -> None:
        self.cleared.emit()

    def append(self, text: str) -> None:
        self.appended.emit(text)

    def show(self, text: str) -> None:
        self.clear()
        self.append(text)


@dataclass
class BridgeContext:
    config: AppConfig
    settings: SettingsService | None
    dispatcher: UiDispatcher
    notifier: Notifier


class Controller(QObject):
    savingChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__()
        self._ctx = ctx
        self._saving = False

    @pyqtProperty(bool, notify=savingChanged)
    def saving(self) -> bool:
        return self._saving

    def _record(self, action: str, detail: str = '', phase: str = '') -> None:
        if action:
            self._ctx.notifier.activityRecorded.emit(action, detail, phase)

    def _note(self, sentence):
        self._ctx.notifier.technicalNote.emit(sentence)

    def _saved_file(self, name):
        self._note(f'Se exportó el archivo {name}.')

    def _export(self, task, on_success) -> None:
        """Una exportación por controlador, con respuestas en el hilo gráfico."""
        if self._saving:
            return
        self._saving = True
        self.savingChanged.emit()

        def finished(callback, value, phase):
            self._saving = False
            self.savingChanged.emit()
            self._record('export', '', phase)
            if phase == 'activityCompleted' and isinstance(value, (str, PurePath)):
                self._saved_file(PurePath(value).name)
            callback(value)

        try:
            self._ctx.dispatcher.background(
                task, lambda value: finished(on_success, value, 'activityCompleted'),
                lambda error: finished(self._fail, error, 'activityFailed'))
        except Exception as error:
            finished(self._fail, error, 'activityFailed')

    @property
    def translator(self) -> Translator:
        settings = self._ctx.settings
        return Translator(settings.current.language.value if settings is not None else 'es')

    def _tr(self, code: str, /, **parameters) -> str:
        return self.translator.tr(code, **parameters)

    def _render(self, value):
        return self.translator.render(value)

    def _json(self, value) -> str:
        return json.dumps(self._render(value))

    def _fail(self, error: Exception) -> None:
        self._ctx.notifier.error(self._render(error))


class TaskController(Controller):
    """Tareas que bloquean (mtr, nmap, speedtest...): corren en otro hilo y marcan `busy`."""
    busyChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._busy = False
        self._console = Console()

    @pyqtProperty(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @pyqtProperty(QObject, constant=True)
    def console(self) -> Console:
        return self._console

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.busyChanged.emit()

    def _task(self, task: Callable[[], Any],
              on_success: Optional[Callable[[Any], None]] = None,
              on_error: Optional[Callable[[Exception], None]] = None,
              *, action: str = '', detail: str = '') -> None:
        if self._busy:
            return
        self._set_busy(True)
        self._record(action, detail, 'activityStarted')

        def succeeded(value: Any) -> None:
            self._set_busy(False)
            self._record(action, detail, 'activityCompleted')
            if action in ('save', 'export') and isinstance(value, str):
                self._saved_file(value)
            if on_success:
                on_success(value)

        def failed(error: Exception) -> None:
            self._set_busy(False)
            self._record(action, detail, 'activityFailed')
            (on_error or self._fail)(error)

        self._ctx.dispatcher.background(task, succeeded, failed)


class SessionController(Controller):
    """Procesos largos con inicio y parada (captura, ping, descubrimiento)."""
    runningChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext, session):
        super().__init__(ctx)
        self._session = session
        self._running = False
        self._activity_action = ''
        self._activity_detail = ''
        self._console = Console()

    @pyqtProperty(bool, notify=runningChanged)
    def running(self) -> bool:
        return self._running

    @pyqtProperty(QObject, constant=True)
    def console(self) -> Console:
        return self._console

    @pyqtSlot()
    def stop(self) -> None:
        if self._running:
            self._record(self._activity_action, self._activity_detail, 'activityStop')
        self._session.stop()
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        if running != self._running:
            self._running = running
            self.runningChanged.emit()

    def _launch(self, starter: Callable[..., Any], action: str, detail: str) -> bool:
        dispatcher = self._ctx.dispatcher
        try:
            starter(on_output=dispatcher.wrap(self._output), on_exit=dispatcher.wrap(self._exited))
        except MulitaError as exc:
            self._record(action, detail, 'activityFailed')
            self._rejected(exc)
            return False
        self._activity_action, self._activity_detail = action, detail
        self._record(action, detail, 'activityStarted')
        self._set_running(True)
        return True

    def _output(self, text: str) -> None:
        self._console.append(text)

    def _rejected(self, error: MulitaError) -> None:
        self._console.show(f'{self._render(error)}\n')

    def _exited(self, code: int) -> None:
        if not self._session.is_running:
            phase = 'activityFailed' if code and self._running else 'activityEnded'
            self._record(self._activity_action, self._activity_detail, phase)
            self._set_running(False)
            self._finished(code)

    def _finished(self, code: int) -> None:
        pass
