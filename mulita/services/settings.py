from __future__ import annotations

from typing import Any, Callable

from mulita.core import settings as rules
from mulita.core.ports import SettingsStore
from mulita.core.settings import DISPLAY_PRESETS, DisplayPreset, Settings

SettingsListener = Callable[[Settings], None]


class SettingsService:

    def __init__(self, store: SettingsStore):
        self._store = store
        self._current = store.load()
        self._listeners: list[SettingsListener] = []

    @property
    def current(self) -> Settings:
        return self._current

    @property
    def presets(self) -> tuple[DisplayPreset, ...]:
        return DISPLAY_PRESETS

    def subscribe(self, listener: SettingsListener) -> None:
        self._listeners.append(listener)

    def update_display(self, width: Any, height: Any, diagonal_inches: Any,
                       fullscreen: Any, ui_scale: Any) -> Settings:
        display = rules.display_settings(width, height, diagonal_inches, fullscreen, ui_scale)
        return self._commit(rules.with_display(self._current, display))

    def apply_preset(self, index: int) -> Settings:
        preset = DISPLAY_PRESETS[index]
        display = self._current.display
        return self.update_display(preset.width, preset.height, preset.diagonal_inches,
                                   display.fullscreen, display.ui_scale)

    def set_theme(self, value: Any) -> Settings:
        return self._commit(rules.with_theme(self._current, rules.theme(value)))

    def _commit(self, settings: Settings) -> Settings:
        if settings != self._current:
            self._store.save(settings)
            self._current = settings
            for listener in self._listeners:
                listener(settings)
        return self._current
