from __future__ import annotations

import ipaddress
import re
import shlex

from mulita.core.errors import ValidationError
from mulita.presentation.i18n import tr
from mulita.core.models import (PING_COUNT, PING_INTERVAL, PING_SIZE,
                                AddressMode, CaptureDirection, CaptureRequest,
                                EthernetConfig, PingRequest, Range)

_HOST = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:%-]*$')
_MAC = re.compile(r'^[0-9A-Fa-f]{2}([:-])(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}$')
_FILENAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
_IFACE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,14}$')
CAPTURE_EXTENSION = '.pcap'
TRACE_EXTENSION = '.csv'
PING_TABLE_EXTENSION = '.csv'
PING_STATICS_SUFFIX = '.statics.csv'


def require(value: str, field: str) -> str:
    value = (value or '').strip()
    if not value:
        raise ValidationError(tr('missingField', field=field))
    return value


def host(value: str) -> str:
    value = (value or '').strip()
    if not value:
        raise ValidationError(tr('needHost'))
    if not _HOST.match(value):
        raise ValidationError(tr('badHost', value=value))
    return value


def mac_address(value: str) -> str:
    value = (value or '').strip()
    if not _MAC.match(value):
        raise ValidationError(tr('badMac', value=value or tr('empty')))
    return value


def scan_arguments(value: str) -> list[str]:
    """Nmap acepta destinos y opciones; se separan sin pasar por el shell."""
    try:
        args = shlex.split(value or '')
    except ValueError as exc:
        raise ValidationError(tr('badArgs', value=exc)) from exc
    if not args:
        raise ValidationError(tr('needScan'))
    return args


def capture_filename(value: str) -> str:
    name = (value or '').strip()
    if name.lower().endswith(CAPTURE_EXTENSION):
        name = name[:-len(CAPTURE_EXTENSION)]
    if not _FILENAME.match(name):
        raise ValidationError(tr('badFileName'))
    return name + CAPTURE_EXTENSION


def ping_basename(value: str) -> str:
    name = (value or '').strip()
    lower = name.lower()
    if lower.endswith(PING_STATICS_SUFFIX):
        name = name[:-len(PING_STATICS_SUFFIX)]
    elif lower.endswith(PING_TABLE_EXTENSION):
        name = name[:-len(PING_TABLE_EXTENSION)]
    if not _FILENAME.match(name):
        raise ValidationError(tr('badFileName'))
    return name


def named_file(value: str, suffix: str) -> str:
    name = (value or '').strip()
    if name.lower().endswith(suffix):
        name = name[:-len(suffix)]
    if not _FILENAME.match(name):
        raise ValidationError(tr('badFileName'))
    return name + suffix


def trace_filename(value: str) -> str:
    name = (value or '').strip()
    if name.lower().endswith(TRACE_EXTENSION):
        name = name[:-len(TRACE_EXTENSION)]
    if not _FILENAME.match(name):
        raise ValidationError(tr('badFileName'))
    return name + TRACE_EXTENSION


def interface_name(value: str) -> str:
    value = require(value, tr('fieldIface'))
    if not _IFACE.match(value):
        raise ValidationError(tr('badIface', value=value))
    return value


def capture_request(interface: str, direction: str, filename: str) -> CaptureRequest:
    interface = require(interface, tr('fieldIface'))
    try:
        parsed_direction = CaptureDirection(require(direction, tr('fieldDirection')))
    except ValueError as exc:
        raise ValidationError(tr('badDirection', value=direction)) from exc
    return CaptureRequest(interface, parsed_direction, capture_filename(filename))


def _in_range(value: float, limits: Range, field: str) -> float:
    if not limits.contains(value):
        raise ValidationError(tr('outOfRange', field=field, minimum=limits.minimum, maximum=limits.maximum))
    return value


def ipv4_address(value: str, field: str) -> str:
    text = (value or '').strip()
    try:
        return str(ipaddress.IPv4Address(text))
    except ValueError as exc:
        raise ValidationError(tr('badIp', field=field, value=text or tr('empty'))) from exc


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
            raise ValidationError(tr('badMask', value=text or tr('empty'))) from exc
    if not 1 <= prefix <= 32:
        raise ValidationError(tr('maskRange'))
    return prefix


def static_ethernet(address: str, netmask: str, gateway: str = '', dns: str = '') -> EthernetConfig:
    ip_text = ipv4_address(address, tr('fieldAddress'))
    prefix = netmask_prefix(netmask)
    gateway_text = ipv4_address(gateway, tr('fieldGateway')) if (gateway or '').strip() else ''
    dns_text = ipv4_address(dns, 'DNS') if (dns or '').strip() else ''
    ip = ipaddress.IPv4Address(ip_text)
    network = ipaddress.IPv4Network(f'{ip_text}/{prefix}', strict=False)
    if prefix <= 30 and (ip == network.network_address or ip == network.broadcast_address):
        raise ValidationError(tr('notHost'))
    if gateway_text:
        route = ipaddress.IPv4Address(gateway_text)
        if route == ip:
            raise ValidationError(tr('gatewayIsHost'))
        if prefix <= 30 and route not in network:
            raise ValidationError(tr('gatewayOffNet'))
    return EthernetConfig(AddressMode.ESTATICA, ip_text, prefix, gateway_text, dns_text)


def wifi_ssid(value: str) -> str:
    text = (value or '').strip()
    if not text or text.startswith('-') or '\n' in text or '\r' in text or len(text) > 32:
        raise ValidationError(tr('badSsid'))
    return text


def wifi_password(value: str, required: bool) -> str:
    text = value or ''
    if '\n' in text or '\r' in text:
        raise ValidationError(tr('passwordBreak'))
    if required and not text.strip():
        raise ValidationError(tr('needPassword'))
    return text


def ping_request(target: str, count: float, interval: float, size: float) -> PingRequest:
    return PingRequest(
        target=host(target),
        count=int(_in_range(int(count), PING_COUNT, 'Envios')),
        interval=_in_range(round(float(interval), 2), PING_INTERVAL, 'Intervalo'),
        size=int(_in_range(int(size), PING_SIZE, 'Tamaño')))
