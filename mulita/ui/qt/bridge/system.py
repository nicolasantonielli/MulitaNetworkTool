from __future__ import annotations

import os
import sys

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor

from mulita.core.errors import MulitaError
from mulita.core.settings import Settings, Theme
from mulita.presentation import texts
from mulita.presentation.theme import Metrics, palette_for
from mulita.ui.qt.bridge.base import BridgeContext, Controller, TaskController
from mulita.version import __version__


class SystemController(TaskController):

    @pyqtProperty(str, constant=True)
    def version(self) -> str:
        return __version__

    @pyqtSlot()
    def update(self) -> None:
        self._task(self._services.maintenance.update,
                   lambda _result: self._ctx.notifier.success('Actualizacion', texts.UPDATE_DONE))

    @pyqtSlot()
    def reset(self) -> None:
        def restarted(result) -> None:
            if result is None:
                os.execv(sys.executable, [sys.executable, *sys.argv])

        self._task(self._services.maintenance.reset, restarted)

    @pyqtSlot()
    def poweroff(self) -> None:
        self._task(self._services.maintenance.poweroff)

    @pyqtSlot(str)
    def share(self, source: str) -> None:
        self._services.share.share(source)
        self._ctx.notifier.info('Compartir', 'La funcion compartir todavia no esta disponible')


class SettingsController(Controller):
    """Tema. La pantalla esta fija en el codigo."""
    changed = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        ctx.services.settings.subscribe(lambda _settings: self.changed.emit())

    @property
    def _current(self) -> Settings:
        return self._services.settings.current

    @pyqtProperty(str, notify=changed)
    def theme(self) -> str:
        return self._current.theme.value

    @pyqtProperty('QVariantList', constant=True)
    def themes(self) -> list[dict]:
        return [{'label': theme.label, 'value': theme.value} for theme in Theme]

    @pyqtSlot(str)
    def setTheme(self, value: str) -> None:
        try:
            self._services.settings.set_theme(value)
        except MulitaError as exc:
            self._fail(exc)


class Appearance(Controller):
    """Paleta y medidas calculadas desde la pantalla configurada. QML lo ve como `ui`."""
    changed = pyqtSignal()

    def _color(name: str, changed=changed):
        return pyqtProperty(QColor, lambda self: QColor(getattr(self._palette, name)), notify=changed)

    def _metric(name: str, kind=int, changed=changed):
        return pyqtProperty(kind, lambda self: getattr(self._metrics, name), notify=changed)

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._load(ctx.services.settings.current)
        ctx.services.settings.subscribe(self._reload)

    def _load(self, settings: Settings) -> None:
        self._settings = settings
        self._palette = palette_for(settings.theme)
        self._metrics = Metrics.for_display(settings.display)

    def _reload(self, settings: Settings) -> None:
        self._load(settings)
        self.changed.emit()

    @pyqtProperty(bool, notify=changed)
    def dark(self) -> bool:
        return self._settings.theme is Theme.OSCURO

    @pyqtProperty(int, notify=changed)
    def windowWidth(self) -> int:
        return self._settings.display.width

    @pyqtProperty(int, notify=changed)
    def windowHeight(self) -> int:
        return self._settings.display.height

    @pyqtProperty(bool, notify=changed)
    def fullscreen(self) -> bool:
        return self._settings.display.fullscreen and not self._ctx.config.test_mode

    @pyqtProperty(float, notify=changed)
    def pixelsPerInch(self) -> float:
        return self._settings.display.pixels_per_inch

    @pyqtProperty(str, constant=True)
    def monoFamily(self) -> str:
        return 'Consolas' if os.name == 'nt' else 'DejaVu Sans Mono'

    @pyqtProperty(bool, constant=True)
    def virtualKeyboard(self) -> bool:
        return self._ctx.config.virtual_keyboard

    background = _color('background')
    surface = _color('surface')
    surfaceAlt = _color('surface_alt')
    surfaceHigh = _color('surface_high')
    border = _color('border')
    text = _color('text')
    textMuted = _color('text_muted')
    primary = _color('primary')
    onAccent = _color('on_accent')
    success = _color('success')
    warning = _color('warning')
    danger = _color('danger')
    consoleBackground = _color('console_background')
    consoleText = _color('console_text')

    mm = _metric('mm', float)
    touch = _metric('touch')
    header = _metric('header')
    gap = _metric('gap')
    padding = _metric('padding')
    radius = _metric('radius')
    icon = _metric('icon')
    fontSmall = _metric('font_small')
    fontBody = _metric('font_body')
    fontTitle = _metric('font_title')
    fontHeading = _metric('font_heading')
    fontDisplay = _metric('font_display')

    del _color, _metric
