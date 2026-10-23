from __future__ import annotations

import logging
import queue
import tkinter as tk
from typing import Any, Callable

from mulita.presentation.dispatcher import UiDispatcher

log = logging.getLogger(__name__)


class TkDispatcher(UiDispatcher):
    """Tk no tiene una cola entre hilos: se vacia una propia cada pocos milisegundos."""

    def __init__(self, root: tk.Misc, interval_ms: int = 30):
        self._root = root
        self._interval_ms = interval_ms
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._root.after(self._interval_ms, self._drain)

    def post(self, callback: Callable[..., Any], *args: Any) -> None:
        self._queue.put((callback, args))

    def _drain(self) -> None:
        while True:
            try:
                callback, args = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                callback(*args)
            except Exception:
                log.exception('Callback de interfaz')
        try:
            self._root.after(self._interval_ms, self._drain)
        except tk.TclError:
            pass
