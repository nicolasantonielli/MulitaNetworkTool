from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Callable

from mulita.core import settings as rules
from mulita.core.errors import MulitaError, ValidationError
from mulita.core.ports import SettingsStore
from mulita.core.settings import Settings
from mulita.core.platform import Backlight
from mulita.core.messages import message

log = logging.getLogger(__name__)

SettingsListener = Callable[[Settings], None]


class SettingsService:

    def __init__(self, store: SettingsStore, backlight: Backlight):
        self._store = store
        self._backlight = backlight
        self._current = store.load()
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

    def set_resize_tiles(self, value: bool) -> Settings:
        return self._commit(replace(self._current, display=replace(self._current.display, resize_tiles=value)))

    def set_rotation(self, angle: int) -> Settings:
        if type(angle) is not int or angle not in (0, 90, 180, 270):
            raise ValidationError(message('rotationInvalid'))
        return self._commit(replace(self._current, display=replace(self._current.display, rotation=angle)))

    def backlight_ready(self) -> bool:
        return self._backlight.available()

    def set_home_screens(self, screens: Any) -> Settings:
        return self._commit(rules.with_home_screens(self._current, screens))

    def reset_tile_order(self) -> Settings:
        return self._commit(rules.reset_tile_order(self._current))

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
            self._store.save(settings)
            self._current = settings
            for listener in self._listeners:
                listener(settings)
        return self._current
