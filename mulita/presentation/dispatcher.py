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

    @abstractmethod
    def post(self, callback: Callable[..., Any], *args: Any) -> None: ...

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
