from __future__ import annotations

from typing import Any, Callable

from mulita.core import settings as rules
from mulita.core.ports import SettingsStore
from mulita.core.settings import Settings
from mulita.presentation import i18n

SettingsListener = Callable[[Settings], None]


class SettingsService:

    def __init__(self, store: SettingsStore):
        self._store = store
        self._current = store.load()
        i18n.use(self._current.language.value)
        self._listeners: list[SettingsListener] = []

    @property
    def current(self) -> Settings:
        return self._current

    def subscribe(self, listener: SettingsListener) -> None:
        self._listeners.append(listener)

    def set_theme(self, value: Any) -> Settings:
        return self._commit(rules.with_theme(self._current, rules.theme(value)))

    def set_language(self, value: Any) -> Settings:
        return self._commit(rules.with_language(self._current, rules.language(value)))

    def set_scale(self, value: Any) -> Settings:
        return self._commit(rules.with_scale(self._current, value))

    def _commit(self, settings: Settings) -> Settings:
        if settings != self._current:
            i18n.use(settings.language.value)
            self._store.save(settings)
            self._current = settings
            for listener in self._listeners:
                listener(settings)
        return self._current
