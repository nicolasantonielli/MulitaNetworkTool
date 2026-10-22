from __future__ import annotations

from ttkbootstrap.toast import ToastNotification


class ToastNotifier:

    def __init__(self, duration_ms: int = 6000):
        self._duration_ms = duration_ms

    def info(self, title: str, message: str) -> None:
        ToastNotification(title=title, message=message,
                          duration=self._duration_ms, alert=True).show_toast()

    def error(self, message: str, title: str = 'Error') -> None:
        ToastNotification(title=title, message=message, duration=self._duration_ms,
                          alert=True, bootstyle='danger').show_toast()
