"""Piezas comunes de los controladores que QML ve como objetos de contexto."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from mulita.config import AppConfig
from mulita.core.errors import MulitaError
from mulita.presentation.dispatcher import UiDispatcher
from mulita.services import Services


class Notifier(QObject):
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
    services: Services
    dispatcher: UiDispatcher
    notifier: Notifier


class Controller(QObject):

    def __init__(self, ctx: BridgeContext):
        super().__init__()
        self._ctx = ctx
        self._services = ctx.services

    def _fail(self, error: Exception) -> None:
        self._ctx.notifier.error(str(error))


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
              on_error: Optional[Callable[[Exception], None]] = None) -> None:
        if self._busy:
            return
        self._set_busy(True)

        def succeeded(value: Any) -> None:
            self._set_busy(False)
            if on_success:
                on_success(value)

        def failed(error: Exception) -> None:
            self._set_busy(False)
            (on_error or self._fail)(error)

        self._ctx.dispatcher.background(task, succeeded, failed)


class SessionController(Controller):
    """Procesos largos con inicio y parada (captura, ping, descubrimiento)."""
    runningChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext, session):
        super().__init__(ctx)
        self._session = session
        self._running = False
        self._console = Console()

    @pyqtProperty(bool, notify=runningChanged)
    def running(self) -> bool:
        return self._running

    @pyqtProperty(QObject, constant=True)
    def console(self) -> Console:
        return self._console

    @pyqtSlot()
    def stop(self) -> None:
        self._session.stop()
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        if running != self._running:
            self._running = running
            self.runningChanged.emit()

    def _launch(self, starter: Callable[..., Any]) -> bool:
        dispatcher = self._ctx.dispatcher
        try:
            starter(on_output=dispatcher.wrap(self._output), on_exit=dispatcher.wrap(self._exited))
        except MulitaError as exc:
            self._rejected(exc)
            return False
        self._set_running(True)
        return True

    def _output(self, text: str) -> None:
        self._console.append(text)

    def _rejected(self, error: MulitaError) -> None:
        self._console.show(f'{error}\n')

    def _exited(self, code: int) -> None:
        if not self._session.is_running:
            self._set_running(False)
            self._finished(code)

    def _finished(self, code: int) -> None:
        pass
