from __future__ import annotations

import functools
import logging
import queue
import threading
import tkinter as tk
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


class TkDispatcher:
    """Tk no es thread-safe: todo lo que llega de otros hilos se encola y se
    ejecuta en el hilo de la interfaz."""

    def __init__(self, root: tk.Misc, interval_ms: int = 30):
        self._root = root
        self._interval_ms = interval_ms
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._root.after(self._interval_ms, self._drain)

    def post(self, callback: Callable[..., Any], *args: Any) -> None:
        self._queue.put((callback, args))

    def wrap(self, callback: Callable[..., Any]) -> Callable[..., None]:
        @functools.wraps(callback)
        def posted(*args: Any) -> None:
            self.post(callback, *args)
        return posted

    def background(self, task: Callable[[], Any],
                   on_success: Optional[Callable[[Any], None]] = None,
                   on_error: Optional[Callable[[Exception], None]] = None) -> None:
        def work() -> None:
            try:
                value = task()
            except Exception as exc:
                log.exception('Tarea en segundo plano')
                if on_error:
                    self.post(on_error, exc)
                return
            if on_success:
                self.post(on_success, value)

        threading.Thread(target=work, daemon=True).start()

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
