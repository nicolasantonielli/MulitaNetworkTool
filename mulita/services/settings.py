from __future__ import annotations

from typing import Any, Callable

from mulita.core import settings as rules
from mulita.core.ports import SettingsStore
from mulita.core.settings import Settings

SettingsListener = Callable[[Settings], None]


class SettingsService:

    def __init__(self, store: SettingsStore):
        self._store = store
        self._current = store.load()
        self._listeners: list[SettingsListener] = []

    @property
    def current(self) -> Settings:
        return self._current

    def subscribe(self, listener: SettingsListener) -> None:
        self._listeners.append(listener)

    def set_theme(self, value: Any) -> Settings:
        return self._commit(rules.with_theme(self._current, rules.theme(value)))

    def set_scale(self, value: Any) -> Settings:
        return self._commit(rules.with_scale(self._current, value))

    def _commit(self, settings: Settings) -> Settings:
        if settings != self._current:
            self._store.save(settings)
            self._current = settings
            for listener in self._listeners:
                listener(settings)
        return self._current
