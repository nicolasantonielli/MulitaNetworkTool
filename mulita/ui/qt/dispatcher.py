from __future__ import annotations

import logging
from typing import Any, Callable

from PyQt5.QtCore import QObject, Qt, pyqtSignal, pyqtSlot

from mulita.presentation.dispatcher import UiDispatcher

log = logging.getLogger(__name__)


class _Invoker(QObject):
    invoke = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.invoke.connect(self._run, Qt.QueuedConnection)

    @pyqtSlot(object)
    def _run(self, call: tuple) -> None:
        callback, args = call
        try:
            callback(*args)
        except Exception:
            log.exception('Callback de interfaz')


class QtDispatcher(UiDispatcher):
    """Una senal encolada lleva cada llamada al hilo de la interfaz."""

    def __init__(self):
        self._invoker = _Invoker()

    def post(self, callback: Callable[..., Any], *args: Any) -> None:
        self._invoker.invoke.emit((callback, args))
