from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Protocol

from mulita.core import settings as rules
from mulita.core.errors import MulitaError
from mulita.core.ports import SettingsStore
from mulita.core.settings import Settings
from mulita.adapters.backlight import PanelBacklight
from mulita.presentation import i18n

log = logging.getLogger(__name__)

SettingsListener = Callable[[Settings], None]


class Backlight(Protocol):

    def available(self) -> bool: ...

    def apply(self, percent: int) -> None: ...


class SettingsService:

    def __init__(self, store: SettingsStore, backlight: Optional[Backlight] = None):
        self._store = store
        self._backlight = backlight or PanelBacklight()
        self._current = store.load()
        i18n.use(self._current.language.value)
        self._listeners: list[SettingsListener] = []
        self._restore_brightness()

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

    def backlight_ready(self) -> bool:
        return self._backlight.available()

    def set_brightness(self, value: Any) -> Settings:
        updated = self._commit(rules.with_brightness(self._current, value))
        self._backlight.apply(updated.brightness)
        return updated

    def _restore_brightness(self) -> None:
        try:
            self._backlight.apply(self._current.brightness)
        except MulitaError as exc:
            log.warning('%s', exc)

    def _commit(self, settings: Settings) -> Settings:
        if settings != self._current:
            i18n.use(settings.language.value)
            self._store.save(settings)
            self._current = settings
            for listener in self._listeners:
                listener(settings)
        return self._current
