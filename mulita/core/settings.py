"""Preferencias del equipo. La pantalla es fija; del archivo solo se lee el tema."""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping

from mulita.core.errors import ValidationError

MM_PER_INCH = 25.4

# Panel del equipo. Estos numeros definen el tamaño fisico de los controles.
PANEL_WIDTH = 800
PANEL_HEIGHT = 480
PANEL_DIAGONAL_INCHES = 5.0


class Theme(Enum):
    OSCURO = 'dark'
    CLARO = 'light'

    @property
    def label(self) -> str:
        return 'Oscuro' if self is Theme.OSCURO else 'Claro'


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
class Settings:
    display: DisplaySettings = field(default_factory=DisplaySettings)
    theme: Theme = Theme.OSCURO

    def to_dict(self) -> dict[str, Any]:
        return {'theme': self.theme.value}


def theme(value: Any) -> Theme:
    try:
        return Theme(value)
    except ValueError as exc:
        raise ValidationError(f'Tema invalido: {value}') from exc


def settings_from_dict(data: Mapping[str, Any]) -> Settings:
    """La pantalla no se configura. Del archivo solo se lee el tema."""
    defaults = Settings()
    try:
        chosen_theme = theme(data.get('theme', defaults.theme.value))
    except ValidationError:
        chosen_theme = defaults.theme
    return Settings(theme=chosen_theme)


def with_theme(settings: Settings, chosen: Theme) -> Settings:
    return replace(settings, theme=chosen)
