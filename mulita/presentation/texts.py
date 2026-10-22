"""Textos de pantalla, independientes del toolkit grafico."""
from __future__ import annotations

from mulita.core.models import ClimateReading, SpeedTestResult

TRACING = 'Trazando...Aguarde por favor\n'
SCANNING = 'Escaneando...Aguarde por favor\n'
MEASURING = 'Realizando medicion... Aguarde'
UPDATE_DONE = 'Actualizacion realizada. reinicie para aplicar'


def version(number: str) -> str:
    return f'Versión {number}'


def temperature(reading: ClimateReading | None) -> str:
    if reading is None:
        return 'Temperatura: sin lectura'
    return f'Temperatura: {reading.temperature:g}°c'


def humidity(reading: ClimateReading | None) -> str:
    if reading is None:
        return 'Humedad: sin lectura'
    return f'Humedad: {reading.humidity:g}%'


def download(result: SpeedTestResult) -> str:
    return f'Download: {result.download_mbps:.2f} Mbps'


def upload(result: SpeedTestResult) -> str:
    return f'Upload: {result.upload_mbps:.2f} Mbps'


def public_ip(address: str) -> str:
    return f'La ip publica es {address}'


def ping_count(value: float) -> str:
    return f'{int(value)} envios'


def ping_interval(value: float) -> str:
    return f'{value:.1f} segundos'


def ping_size(value: float) -> str:
    return f'{int(value)} bytes'
