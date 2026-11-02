from __future__ import annotations

import functools
import logging
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


class UiDispatcher(ABC):
    """Los toolkits graficos no son thread-safe: lo que llega de otros hilos
    se reenvia al hilo de la interfaz con `post`."""

    def __init__(self):
        self._lock = threading.RLock()
        self._workers: set[threading.Thread] = set()
        self._draining = False
        self._closed = False
        self._deferred = []

    @abstractmethod
    def post(self, callback: Callable[..., Any], *args: Any) -> None: ...

    def _deliver(self, callback, *args):
        if self._closed:
            return
        if self._draining:
            self._deferred.append((callback, args))
        else:
            callback(*args)

    def wrap(self, callback: Callable[..., Any]) -> Callable[..., None]:
        @functools.wraps(callback)
        def posted(*args: Any) -> None:
            self.post(self._deliver, callback, *args)
        return posted

    def background(self, task, on_success=None, on_error=None) -> None:
        def work():
            try:
                value = task()
            except Exception as exc:
                log.exception('Tarea en segundo plano')
                if on_error:
                    self.post(self._deliver, on_error, exc)
            else:
                if on_success:
                    self.post(self._deliver, on_success, value)
            finally:
                with self._lock:
                    self._workers.discard(threading.current_thread())
        with self._lock:
            if self._draining or self._closed:
                return
            worker = threading.Thread(target=work, daemon=False)
            self._workers.add(worker)
            try:
                worker.start()
            except Exception:
                self._workers.discard(worker)
                raise

    def shutdown(self) -> None:
        """Termina las escrituras antes de destruir UI; descarta callbacks tardíos."""
        with self._lock:
            self._closed = self._draining = True
            self._deferred.clear()
            pending = tuple(self._workers)
        for worker in pending:
            if worker is not threading.current_thread():
                worker.join()

    def finish_background(self, action, on_success=None, on_error=None) -> bool:
        """Reinicio/apagado: deja de aceptar trabajo, drena y ejecuta la acción."""
        with self._lock:
            if self._draining or self._closed:
                return False
            self._draining = True
            pending = tuple(self._workers)

            def complete(callback, value, failed):
                if self._closed:
                    return
                if failed:
                    self._draining = False
                    deferred, self._deferred = self._deferred, []
                    for call, args in deferred:
                        self.post(self._deliver, call, *args)
                if callback:
                    callback(value)

            def finish():
                try:
                    for worker in pending:
                        worker.join()
                    value = action()
                except Exception as exc:
                    self.post(complete, on_error, exc, True)
                else:
                    self.post(complete, on_success, value, False)
                finally:
                    with self._lock:
                        self._workers.discard(threading.current_thread())

            worker = threading.Thread(target=finish, daemon=False)
            self._workers.add(worker)
            try:
                worker.start()
            except Exception:
                self._workers.discard(worker)
                self._draining = False
                raise
            return True
