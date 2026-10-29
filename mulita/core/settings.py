"""Preferencias del equipo. El panel es fijo; del archivo se leen tema, escala, idioma, brillo y el orden de los cuadros."""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping

from mulita.core.errors import ValidationError
from mulita.presentation.i18n import tr

MM_PER_INCH = 25.4

# Panel del equipo. Estos numeros definen el tamaño fisico de los controles.
PANEL_WIDTH = 800
PANEL_HEIGHT = 480
PANEL_DIAGONAL_INCHES = 5.0
UI_SCALE_MIN = 0.5
UI_SCALE_MAX = 1.25
UI_SCALE_STEP = 0.05
BRIGHTNESS_MIN = 1
BRIGHTNESS_MAX = 100

# Orden de fabrica. Cada pantalla del inicio lleva de 1 a 6 cuadros, sin importar el rubro.
NETWORK_ORDER = ('capture', 'traces', 'tap', 'scan', 'tools', 'settings')
CYBER_ORDER = ('vuln', 'wifi', 'arp', 'nmap', 'tls', 'servers')
ALL_TILES = NETWORK_ORDER + CYBER_ORDER + ('switchport',)
SCREEN_LIMIT = 6
DEFAULT_SCREENS = (NETWORK_ORDER, CYBER_ORDER, ('switchport',))


class Theme(Enum):
    OSCURO = 'dark'
    CLARO = 'light'

    @property
    def label(self) -> str:
        return 'Oscuro' if self is Theme.OSCURO else 'Claro'


class Language(Enum):
    ES = 'es'
    EN = 'en'

    @property
    def label(self) -> str:
        return 'Español' if self is Language.ES else 'English'

    @property
    def available(self) -> bool:
        return True


@dataclass(frozen=True)
class DisplaySettings:
    width: int = PANEL_WIDTH
    height: int = PANEL_HEIGHT
    diagonal_inches: float = PANEL_DIAGONAL_INCHES
    fullscreen: bool = True
    ui_scale: float = 1.0

    @property
    def pixels_per_inch(self) -> float:
        return math.hypot(self.width, self.height) / self.diagonal_inches

    @property
    def pixels_per_mm(self) -> float:
        """Base de todas las medidas de la interfaz: lo fisico se mantiene al cambiar de panel."""
        return self.pixels_per_inch / MM_PER_INCH * self.ui_scale


@dataclass(frozen=True)
class HomeOrder:
    screens: tuple[tuple[str, ...], ...] = DEFAULT_SCREENS


@dataclass(frozen=True)
class Settings:
    display: DisplaySettings = field(default_factory=DisplaySettings)
    theme: Theme = Theme.OSCURO
    language: Language = Language.ES
    brightness: int = BRIGHTNESS_MAX
    home: HomeOrder = field(default_factory=HomeOrder)

    def to_dict(self) -> dict[str, Any]:
        return {
            'theme': self.theme.value,
            'scale': self.display.ui_scale,
            'language': self.language.value,
            'brightness': self.brightness,
            'homeOrder': {
                'screens': [list(screen) for screen in self.home.screens],
            },
        }


def language(value: Any) -> Language:
    try:
        return Language(value)
    except ValueError as exc:
        raise ValidationError(tr('badLanguage', value=value)) from exc


def theme(value: Any) -> Theme:
    try:
        return Theme(value)
    except ValueError as exc:
        raise ValidationError(tr('badTheme', value=value)) from exc


def brightness(value: Any) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError) as exc:
        raise ValidationError(tr('badBrightness', value=value)) from exc
    return min(BRIGHTNESS_MAX, max(BRIGHTNESS_MIN, number))


def ui_scale(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(tr('badScale', value=value)) from exc
    number = min(UI_SCALE_MAX, max(UI_SCALE_MIN, number))
    steps = round((number - UI_SCALE_MIN) / UI_SCALE_STEP)
    return round(UI_SCALE_MIN + steps * UI_SCALE_STEP, 2)


def _complete(default: tuple[str, ...], value: Any) -> tuple[str, ...]:
    """Completa un grupo viejo (Red o Ciberseguridad) para poder leer ajustes ya guardados."""
    if not isinstance(value, list):
        return default
    kept: list[str] = []
    allowed = set(default)
    for item in value:
        if isinstance(item, str) and item in allowed and item not in kept:
            kept.append(item)
    for item in default:
        if item not in kept:
            kept.append(item)
    return tuple(kept)


def normalize_screens(value: Any) -> tuple[tuple[str, ...], ...]:
    """De 1 a 6 cuadros por pantalla. Lo desconocido se descarta y lo que falte se agrega al final."""
    allowed = set(ALL_TILES)
    seen: set[str] = set()
    screens: list[list[str]] = []
    if isinstance(value, list):
        for raw in value:
            if not isinstance(raw, list):
                continue
            page: list[str] = []
            for item in raw:
                if not isinstance(item, str) or item not in allowed or item in seen:
                    continue
                if len(page) >= SCREEN_LIMIT:
                    screens.append(page)
                    page = []
                page.append(item)
                seen.add(item)
            if page:
                screens.append(page)
    rest = [item for item in ALL_TILES if item not in seen]
    if not screens:
        page = []
        built: list[tuple[str, ...]] = []
        for item in rest:
            if len(page) >= SCREEN_LIMIT:
                built.append(tuple(page))
                page = []
            page.append(item)
        if page:
            built.append(tuple(page))
        return tuple(built)
    current = list(screens[-1])
    built = [tuple(page) for page in screens[:-1]]
    for item in rest:
        if len(current) >= SCREEN_LIMIT:
            built.append(tuple(current))
            current = []
        current.append(item)
    if current:
        built.append(tuple(current))
    return tuple(built)


def home_order_from(value: Any) -> HomeOrder:
    raw = value if isinstance(value, Mapping) else {}
    if 'screens' in raw:
        return HomeOrder(screens=normalize_screens(raw.get('screens')))
    # Ajustes anteriores: dos grupos fijos. Pasan a ser la pantalla 1 y la 2.
    return HomeOrder(screens=normalize_screens([
        list(_complete(NETWORK_ORDER, raw.get('network', list(NETWORK_ORDER)))),
        list(_complete(CYBER_ORDER, raw.get('cyber', list(CYBER_ORDER)))),
    ]))


def settings_from_dict(data: Mapping[str, Any]) -> Settings:
    """El tamaño del panel no se configura. Del archivo se leen tema, escala, idioma, brillo y el orden de los cuadros."""
    defaults = Settings()
    try:
        chosen_theme = theme(data.get('theme', defaults.theme.value))
    except ValidationError:
        chosen_theme = defaults.theme
    try:
        scale = ui_scale(data.get('scale', defaults.display.ui_scale))
    except ValidationError:
        scale = defaults.display.ui_scale
    try:
        level = brightness(data.get('brightness', defaults.brightness))
    except ValidationError:
        level = defaults.brightness
    chosen_language = _stored_language(data.get('language', defaults.language.value))
    return Settings(display=replace(defaults.display, ui_scale=scale), theme=chosen_theme,
                    language=chosen_language, brightness=level,
                    home=home_order_from(data.get('homeOrder')))


def _stored_language(value: Any) -> Language:
    try:
        chosen = Language(value)
    except ValueError:
        return Language.ES
    return chosen if chosen.available else Language.ES


def with_theme(settings: Settings, chosen: Theme) -> Settings:
    return replace(settings, theme=chosen)


def with_language(settings: Settings, chosen: Language) -> Settings:
    return replace(settings, language=chosen)


def with_scale(settings: Settings, scale: float) -> Settings:
    return replace(settings, display=replace(settings.display, ui_scale=ui_scale(scale)))


def with_brightness(settings: Settings, level: float) -> Settings:
    return replace(settings, brightness=brightness(level))


def with_home_screens(settings: Settings, screens: Any) -> Settings:
    if not isinstance(screens, list):
        raise ValidationError(tr('badTileOrder'))
    return replace(settings, home=HomeOrder(screens=normalize_screens(screens)))


def reset_tile_order(settings: Settings) -> Settings:
    return replace(settings, home=HomeOrder())
