from __future__ import annotations

import json
import os
import sys

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QGuiApplication

from mulita.core.errors import MulitaError, ValidationError
from mulita.core.settings import Language, Settings, Theme
from mulita.presentation import i18n
from mulita.presentation.theme import Metrics, palette_for
from mulita.ui.qt.bridge.base import BridgeContext, Controller, TaskController
from mulita.version import __version__


class SystemController(TaskController):

    @pyqtSlot(str)
    def copyText(self, text: str) -> None:
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        self._ctx.notifier.success(i18n.tr('copy'), i18n.tr('textCopied'))

    @pyqtProperty(str, constant=True)
    def version(self) -> str:
        return __version__

    @pyqtSlot()
    def update(self) -> None:
        self._task(self._services.maintenance.update,
                   lambda _result: self._ctx.notifier.success(i18n.tr('updateWord'), i18n.tr('updateDone')))

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
        self._ctx.notifier.info(i18n.tr('share'), i18n.tr('shareSoon'))


class SettingsController(Controller):
    """Tema, escala, idioma y brillo. El panel queda fijo en el codigo."""
    changed = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._brightness_error = ''
        ctx.services.settings.subscribe(lambda _settings: self.changed.emit())

    @property
    def _current(self) -> Settings:
        return self._services.settings.current

    @pyqtProperty(str, notify=changed)
    def theme(self) -> str:
        return self._current.theme.value

    @pyqtProperty('QVariantList', notify=changed)
    def themes(self) -> list[dict]:
        return [
            {'label': i18n.tr('themeDark'), 'value': Theme.OSCURO.value},
            {'label': i18n.tr('themeLight'), 'value': Theme.CLARO.value},
        ]

    @pyqtProperty(float, notify=changed)
    def uiScale(self) -> float:
        return self._current.display.ui_scale

    @pyqtProperty(int, notify=changed)
    def brightness(self) -> int:
        return self._current.brightness

    @pyqtProperty(bool, constant=True)
    def brightnessReady(self) -> bool:
        return self._services.settings.backlight_ready()

    @pyqtProperty(str, notify=changed)
    def language(self) -> str:
        return self._current.language.value

    @pyqtProperty('QVariantList', constant=True)
    def languages(self) -> list[dict]:
        return [{'label': item.label, 'value': item.value} for item in Language]

    @pyqtSlot(str)
    def setLanguage(self, value: str) -> None:
        try:
            self._services.settings.set_language(value)
        except MulitaError as exc:
            self._fail(exc)

    @pyqtSlot(str)
    def setTheme(self, value: str) -> None:
        try:
            self._services.settings.set_theme(value)
        except MulitaError as exc:
            self._fail(exc)

    @pyqtSlot(float)
    def setScale(self, value: float) -> None:
        try:
            self._services.settings.set_scale(value)
        except MulitaError as exc:
            self._fail(exc)

    @pyqtProperty('QVariantMap', notify=changed)
    def tileOrder(self) -> dict:
        return {'screens': [list(screen) for screen in self._current.home.screens]}

    @pyqtSlot(str)
    def setHomeScreens(self, order_json: str) -> None:
        try:
            screens = json.loads(order_json or '[]')
            self._services.settings.set_home_screens(screens)
        except (MulitaError, ValueError) as exc:
            self._fail(exc if isinstance(exc, MulitaError) else ValidationError(i18n.tr('badTileOrder')))

    @pyqtSlot()
    def resetTileOrder(self) -> None:
        self._services.settings.reset_tile_order()
        self._ctx.notifier.success(i18n.tr('tileOrderTitle'), i18n.tr('tileOrderResetDone'))

    @pyqtSlot(float)
    def setBrightness(self, value: float) -> None:
        try:
            self._services.settings.set_brightness(value)
        except MulitaError as exc:
            message = str(exc)
            if message != self._brightness_error:
                self._brightness_error = message
                self._fail(exc)
            return
        self._brightness_error = ''


class I18nController(Controller):
    """Catalogo de textos. QML lo lee como `i18n.pack` y se actualiza con el idioma."""
    changed = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._language = ctx.services.settings.current.language.value
        i18n.use(self._language)
        ctx.services.settings.subscribe(self._apply)

    def _apply(self, settings: Settings) -> None:
        chosen = settings.language.value
        i18n.use(chosen)
        if chosen == self._language:
            return
        self._language = chosen
        self.changed.emit()

    @pyqtProperty(str, notify=changed)
    def language(self) -> str:
        return self._language

    @pyqtProperty('QVariantMap', notify=changed)
    def pack(self) -> dict[str, str]:
        return i18n.pack(self._language)


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
