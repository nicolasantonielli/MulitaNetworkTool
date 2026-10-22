from __future__ import annotations

import re
import shlex

from mulita.core.errors import ValidationError
from mulita.core.models import (PING_COUNT, PING_INTERVAL, PING_SIZE,
                                CaptureDirection, CaptureRequest, PingRequest,
                                Range)

_HOST = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:%-]*$')
_MAC = re.compile(r'^[0-9A-Fa-f]{2}([:-])(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}$')
_FILENAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
CAPTURE_EXTENSION = '.pcap'


def require(value: str, field: str) -> str:
    value = (value or '').strip()
    if not value:
        raise ValidationError(f'Falta seleccionar {field}')
    return value


def host(value: str) -> str:
    value = (value or '').strip()
    if not value:
        raise ValidationError('Ingrese una IP o nombre de destino')
    if not _HOST.match(value):
        raise ValidationError(f'Destino invalido: {value}')
    return value


def mac_address(value: str) -> str:
    value = (value or '').strip()
    if not _MAC.match(value):
        raise ValidationError(f'MAC invalida: {value or "(vacia)"}')
    return value


def scan_arguments(value: str) -> list[str]:
    """Nmap acepta destinos y opciones; se separan sin pasar por el shell."""
    try:
        args = shlex.split(value or '')
    except ValueError as exc:
        raise ValidationError(f'Argumentos invalidos: {exc}') from exc
    if not args:
        raise ValidationError('Ingrese una IP o red de destino')
    return args


def capture_filename(value: str) -> str:
    name = (value or '').strip()
    if name.lower().endswith(CAPTURE_EXTENSION):
        name = name[:-len(CAPTURE_EXTENSION)]
    if not _FILENAME.match(name):
        raise ValidationError(
            'Nombre de archivo invalido: use letras, numeros, punto, guion o guion bajo')
    return name + CAPTURE_EXTENSION


def capture_request(interface: str, direction: str, filename: str) -> CaptureRequest:
    interface = require(interface, 'la interface')
    try:
        parsed_direction = CaptureDirection(require(direction, 'la direccion'))
    except ValueError as exc:
        raise ValidationError(f'Direccion invalida: {direction}') from exc
    return CaptureRequest(interface, parsed_direction, capture_filename(filename))


def _in_range(value: float, limits: Range, field: str) -> float:
    if not limits.contains(value):
        raise ValidationError(
            f'{field} fuera de rango ({limits.minimum:g} a {limits.maximum:g})')
    return value


def ping_request(target: str, count: float, interval: float, size: float) -> PingRequest:
    return PingRequest(
        target=host(target),
        count=int(_in_range(int(count), PING_COUNT, 'Envios')),
        interval=_in_range(round(float(interval), 2), PING_INTERVAL, 'Intervalo'),
        size=int(_in_range(int(size), PING_SIZE, 'Tamaño')))
