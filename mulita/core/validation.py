from __future__ import annotations

import ipaddress
import re
import shlex

from mulita.core.errors import ValidationError
from mulita.core.models import (PING_COUNT, PING_INTERVAL, PING_SIZE,
                                AddressMode, CaptureDirection, CaptureRequest,
                                EthernetConfig, PingRequest, Range)

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


def ipv4_address(value: str, field: str) -> str:
    text = (value or '').strip()
    try:
        return str(ipaddress.IPv4Address(text))
    except ValueError as exc:
        raise ValidationError(f'{field} invalida: {text or "(vacia)"}') from exc


def netmask_prefix(value: str) -> int:
    """Acepta 255.255.255.0, 24 o /24."""
    text = (value or '').strip()
    if text.startswith('/'):
        text = text[1:]
    if text.isdigit():
        prefix = int(text)
    else:
        try:
            prefix = ipaddress.IPv4Network(f'0.0.0.0/{text}').prefixlen
        except ValueError as exc:
            raise ValidationError(f'Mascara invalida: {text or "(vacia)"}') from exc
    if not 1 <= prefix <= 32:
        raise ValidationError('Mascara fuera de rango (1 a 32)')
    return prefix


def static_ethernet(address: str, netmask: str, gateway: str = '', dns: str = '') -> EthernetConfig:
    ip_text = ipv4_address(address, 'Direccion')
    prefix = netmask_prefix(netmask)
    gateway_text = ipv4_address(gateway, 'Puerta de enlace') if (gateway or '').strip() else ''
    dns_text = ipv4_address(dns, 'DNS') if (dns or '').strip() else ''
    ip = ipaddress.IPv4Address(ip_text)
    network = ipaddress.IPv4Network(f'{ip_text}/{prefix}', strict=False)
    if prefix <= 30 and (ip == network.network_address or ip == network.broadcast_address):
        raise ValidationError('La direccion no puede ser la de red ni la de broadcast')
    if gateway_text:
        route = ipaddress.IPv4Address(gateway_text)
        if route == ip:
            raise ValidationError('La puerta de enlace no puede ser la misma direccion')
        if prefix <= 30 and route not in network:
            raise ValidationError('La puerta de enlace no esta en la misma red')
    return EthernetConfig(AddressMode.ESTATICA, ip_text, prefix, gateway_text, dns_text)


def ping_request(target: str, count: float, interval: float, size: float) -> PingRequest:
    return PingRequest(
        target=host(target),
        count=int(_in_range(int(count), PING_COUNT, 'Envios')),
        interval=_in_range(round(float(interval), 2), PING_INTERVAL, 'Intervalo'),
        size=int(_in_range(int(size), PING_SIZE, 'Tamaño')))
