"""Preferencias del equipo: pantalla y apariencia. Sin dependencias de UI."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, Mapping

from mulita.core.errors import ValidationError
from mulita.core.models import Range

MM_PER_INCH = 25.4

DISPLAY_WIDTH = Range(320, 3840, 800)
DISPLAY_HEIGHT = Range(240, 2160, 480)
# El equipo es un panel de 5" a 800x480. La diagonal define el tamaño fisico de los controles.
DISPLAY_DIAGONAL = Range(3, 32, 5)
UI_SCALE = Range(0.75, 1.5, 1)


class Theme(Enum):
    OSCURO = 'dark'
    CLARO = 'light'

    @property
    def label(self) -> str:
        return 'Oscuro' if self is Theme.OSCURO else 'Claro'


@dataclass(frozen=True)
class DisplaySettings:
    width: int = int(DISPLAY_WIDTH.default)
    height: int = int(DISPLAY_HEIGHT.default)
    diagonal_inches: float = DISPLAY_DIAGONAL.default
    fullscreen: bool = True
    ui_scale: float = UI_SCALE.default

    @property
    def pixels_per_inch(self) -> float:
        return math.hypot(self.width, self.height) / self.diagonal_inches

    @property
    def pixels_per_mm(self) -> float:
        """Base de todas las medidas de la interfaz: lo fisico se mantiene al cambiar de panel."""
        return self.pixels_per_inch / MM_PER_INCH * self.ui_scale


@dataclass(frozen=True)
class DisplayPreset:
    name: str
    width: int
    height: int
    diagonal_inches: float


DISPLAY_PRESETS = (
    DisplayPreset('5" 800×480', 800, 480, 5),
    DisplayPreset('7" 800×480', 800, 480, 7),
    DisplayPreset('7" 1024×600', 1024, 600, 7),
    DisplayPreset('7" 1280×800', 1280, 800, 7),
    DisplayPreset('10.1" 1024×600', 1024, 600, 10.1),
    DisplayPreset('10.1" 1280×800', 1280, 800, 10.1),
    DisplayPreset('13.3" 1920×1080', 1920, 1080, 13.3),
    DisplayPreset('15.6" 1920×1080', 1920, 1080, 15.6),
)


@dataclass(frozen=True)
class Settings:
    display: DisplaySettings = field(default_factory=DisplaySettings)
    theme: Theme = Theme.OSCURO

    def to_dict(self) -> dict[str, Any]:
        return {'display': asdict(self.display), 'theme': self.theme.value}


def _number(value: Any, limits: Range, label: str, integer: bool = False) -> float:
    try:
        number = int(round(float(value))) if integer else round(float(value), 2)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f'{label} invalido: {value}') from exc
    if not limits.contains(number):
        raise ValidationError(f'{label} fuera de rango ({limits.minimum:g} a {limits.maximum:g})')
    return number


def display_settings(width: Any, height: Any, diagonal_inches: Any,
                     fullscreen: Any = True, ui_scale: Any = UI_SCALE.default) -> DisplaySettings:
    return DisplaySettings(
        width=int(_number(width, DISPLAY_WIDTH, 'Ancho', integer=True)),
        height=int(_number(height, DISPLAY_HEIGHT, 'Alto', integer=True)),
        diagonal_inches=_number(diagonal_inches, DISPLAY_DIAGONAL, 'Diagonal'),
        fullscreen=bool(fullscreen),
        ui_scale=_number(ui_scale, UI_SCALE, 'Escala'))


def theme(value: Any) -> Theme:
    try:
        return Theme(value)
    except ValueError as exc:
        raise ValidationError(f'Tema invalido: {value}') from exc


def settings_from_dict(data: Mapping[str, Any]) -> Settings:
    """Lo que no se pueda leer vuelve al valor por defecto: el equipo siempre arranca."""
    defaults = Settings()
    display_data = data.get('display') or {}
    try:
        display = display_settings(
            display_data.get('width', defaults.display.width),
            display_data.get('height', defaults.display.height),
            display_data.get('diagonal_inches', defaults.display.diagonal_inches),
            display_data.get('fullscreen', defaults.display.fullscreen),
            display_data.get('ui_scale', defaults.display.ui_scale))
    except ValidationError:
        display = defaults.display
    try:
        chosen_theme = theme(data.get('theme', defaults.theme.value))
    except ValidationError:
        chosen_theme = defaults.theme
    return Settings(display=display, theme=chosen_theme)


def with_display(settings: Settings, display: DisplaySettings) -> Settings:
    return replace(settings, display=display)


def with_theme(settings: Settings, chosen: Theme) -> Settings:
    return replace(settings, theme=chosen)
