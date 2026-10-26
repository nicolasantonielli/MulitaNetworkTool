"""Preferencias del equipo. El panel es fijo; del archivo se leen el tema y la escala."""
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
UI_SCALE_MIN = 0.5
UI_SCALE_MAX = 1.25
UI_SCALE_STEP = 0.05


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
        return 'Español' if self is Language.ES else 'Inglés'

    @property
    def available(self) -> bool:
        """Inglés queda visible hasta que la interfaz se traduzca."""
        return self is Language.ES


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
    language: Language = Language.ES

    def to_dict(self) -> dict[str, Any]:
        return {
            'theme': self.theme.value,
            'scale': self.display.ui_scale,
            'language': self.language.value,
        }


def language(value: Any) -> Language:
    try:
        chosen = Language(value)
    except ValueError as exc:
        raise ValidationError(f'Idioma invalido: {value}') from exc
    if not chosen.available:
        raise ValidationError('El inglés todavía no está disponible')
    return chosen


def theme(value: Any) -> Theme:
    try:
        return Theme(value)
    except ValueError as exc:
        raise ValidationError(f'Tema invalido: {value}') from exc


def ui_scale(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f'Escala invalida: {value}') from exc
    number = min(UI_SCALE_MAX, max(UI_SCALE_MIN, number))
    steps = round((number - UI_SCALE_MIN) / UI_SCALE_STEP)
    return round(UI_SCALE_MIN + steps * UI_SCALE_STEP, 2)


def settings_from_dict(data: Mapping[str, Any]) -> Settings:
    """El tamaño del panel no se configura. Del archivo se leen el tema y la escala."""
    defaults = Settings()
    try:
        chosen_theme = theme(data.get('theme', defaults.theme.value))
    except ValidationError:
        chosen_theme = defaults.theme
    try:
        scale = ui_scale(data.get('scale', defaults.display.ui_scale))
    except ValidationError:
        scale = defaults.display.ui_scale
    chosen_language = _stored_language(data.get('language', defaults.language.value))
    return Settings(display=replace(defaults.display, ui_scale=scale), theme=chosen_theme,
                    language=chosen_language)


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
