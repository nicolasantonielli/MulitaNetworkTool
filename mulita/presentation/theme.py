"""Paleta y medidas de la interfaz, independientes del toolkit.

Las medidas se definen en milimetros y se convierten con la densidad del panel
configurado: un boton mide lo mismo bajo el dedo en 5" que en 10.1"."""
from __future__ import annotations

from dataclasses import dataclass

from mulita.core.settings import DisplaySettings, Theme

MIN_TOUCH_MM = 9


@dataclass(frozen=True)
class Palette:
    background: str
    surface: str
    surface_alt: str
    surface_high: str
    border: str
    text: str
    text_muted: str
    primary: str
    on_accent: str
    success: str
    warning: str
    danger: str
    console_background: str
    console_text: str


DARK = Palette(
    background='#0E1319', surface='#161D26', surface_alt='#1E2733', surface_high='#283443',
    border='#2C3948', text='#E6EDF3', text_muted='#8A98A8', primary='#2E9BFF',
    on_accent='#FFFFFF', success='#22B573', warning='#F2A93B', danger='#F0525C',
    console_background='#0A0F14', console_text='#C9F2D7')

LIGHT = Palette(
    background='#EEF2F6', surface='#FFFFFF', surface_alt='#F3F6F9', surface_high='#E2E8EF',
    border='#D3DBE4', text='#17212B', text_muted='#5D6B7A', primary='#0B76DA',
    on_accent='#FFFFFF', success='#15935B', warning='#C77C0E', danger='#D63441',
    console_background='#111820', console_text='#C9F2D7')


def palette_for(theme: Theme) -> Palette:
    return DARK if theme is Theme.OSCURO else LIGHT


@dataclass(frozen=True)
class Metrics:
    mm: float
    touch: int
    header: int
    gap: int
    padding: int
    radius: int
    icon: int
    font_small: int
    font_body: int
    font_title: int
    font_heading: int
    font_display: int

    @classmethod
    def for_display(cls, display: DisplaySettings) -> Metrics:
        mm = display.pixels_per_mm

        def px(millimeters: float) -> int:
            return max(1, round(millimeters * mm))

        return cls(
            mm=mm,
            touch=px(MIN_TOUCH_MM),
            header=px(11),
            gap=px(2.2),
            padding=px(3),
            radius=px(1.8),
            icon=px(5),
            font_small=px(2.5),
            font_body=px(3.1),
            font_title=px(3.9),
            font_heading=px(5),
            font_display=px(9))
