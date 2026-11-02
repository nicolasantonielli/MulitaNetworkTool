"""Formatos de valores utilizados por los controladores Qt."""
from __future__ import annotations

from mulita.core.models import ClimateReading

MEASURING = 'Realizando medicion... Aguarde'
NO_VALUE = '—'


def temperature_value(reading: ClimateReading | None) -> str:
    return NO_VALUE if reading is None else f'{reading.temperature:g} °C'


def humidity_value(reading: ClimateReading | None) -> str:
    return NO_VALUE if reading is None else f'{reading.humidity:g} %'


def mbps(bits_per_second: float) -> str:
    return f'{bits_per_second / 1_000_000:.2f}'
