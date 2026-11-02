from __future__ import annotations

import ipaddress
import re
import shlex

from mulita.core.errors import ValidationError
from mulita.core.messages import message
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
        raise ValidationError(message('missingField', field=field))
    return value


def host(value: str) -> str:
    value = (value or '').strip()
    if not value:
        raise ValidationError(message('needHost'))
    if not _HOST.match(value):
        raise ValidationError(message('badHost', value=value))
    return value


def mac_address(value: str) -> str:
    value = (value or '').strip()
    if not _MAC.match(value):
        raise ValidationError(message('badMac', value=value or message('empty')))
    return value


def scan_arguments(value: str) -> list[str]:
    """Nmap acepta destinos y opciones; se separan sin pasar por el shell."""
    try:
        args = shlex.split(value or '')
    except ValueError as exc:
        raise ValidationError(message('badArgs', value=exc)) from exc
    if not args:
        raise ValidationError(message('needScan'))
    return args


def capture_filename(value: str) -> str:
    name = (value or '').strip()
    if name.lower().endswith(CAPTURE_EXTENSION):
        name = name[:-len(CAPTURE_EXTENSION)]
    if not _FILENAME.match(name):
        raise ValidationError(message('badFileName'))
    return name + CAPTURE_EXTENSION


def ping_basename(value: str) -> str:
    name = (value or '').strip()
    lower = name.lower()
    if lower.endswith(PING_STATICS_SUFFIX):
        name = name[:-len(PING_STATICS_SUFFIX)]
    elif lower.endswith(PING_TABLE_EXTENSION):
        name = name[:-len(PING_TABLE_EXTENSION)]
    if not _FILENAME.match(name):
        raise ValidationError(message('badFileName'))
    return name


def named_file(value: str, suffix: str) -> str:
    name = (value or '').strip()
    if name.lower().endswith(suffix):
        name = name[:-len(suffix)]
    if not _FILENAME.match(name):
        raise ValidationError(message('badFileName'))
    return name + suffix


def trace_filename(value: str) -> str:
    name = (value or '').strip()
    if name.lower().endswith(TRACE_EXTENSION):
        name = name[:-len(TRACE_EXTENSION)]
    if not _FILENAME.match(name):
        raise ValidationError(message('badFileName'))
    return name + TRACE_EXTENSION


def interface_name(value: str) -> str:
    value = require(value, message('fieldIface'))
    if not _IFACE.match(value):
        raise ValidationError(message('badIface', value=value))
    return value


def capture_request(interface: str, direction: str, filename: str) -> CaptureRequest:
    interface = require(interface, message('fieldIface'))
    try:
        parsed_direction = CaptureDirection(require(direction, message('fieldDirection')))
    except ValueError as exc:
        raise ValidationError(message('badDirection', value=direction)) from exc
    return CaptureRequest(interface, parsed_direction, capture_filename(filename))


def _in_range(value: float, limits: Range, field: str) -> float:
    if not limits.contains(value):
        raise ValidationError(message('outOfRange', field=field, minimum=limits.minimum, maximum=limits.maximum))
    return value


def ipv4_address(value: str, field: str) -> str:
    text = (value or '').strip()
    try:
        return str(ipaddress.IPv4Address(text))
    except ValueError as exc:
        raise ValidationError(message('badIp', field=field, value=text or message('empty'))) from exc


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
            raise ValidationError(message('badMask', value=text or message('empty'))) from exc
    if not 1 <= prefix <= 32:
        raise ValidationError(message('maskRange'))
    return prefix


def static_ethernet(address: str, netmask: str, gateway: str = '', dns: str = '') -> EthernetConfig:
    ip_text = ipv4_address(address, message('fieldAddress'))
    prefix = netmask_prefix(netmask)
    gateway_text = ipv4_address(gateway, message('fieldGateway')) if (gateway or '').strip() else ''
    dns_text = ipv4_address(dns, 'DNS') if (dns or '').strip() else ''
    ip = ipaddress.IPv4Address(ip_text)
    network = ipaddress.IPv4Network(f'{ip_text}/{prefix}', strict=False)
    if prefix <= 30 and (ip == network.network_address or ip == network.broadcast_address):
        raise ValidationError(message('notHost'))
    if gateway_text:
        route = ipaddress.IPv4Address(gateway_text)
        if route == ip:
            raise ValidationError(message('gatewayIsHost'))
        if prefix <= 30 and route not in network:
            raise ValidationError(message('gatewayOffNet'))
    return EthernetConfig(AddressMode.ESTATICA, ip_text, prefix, gateway_text, dns_text)


def wifi_ssid(value: str) -> str:
    text = (value or '').strip()
    if not text or text.startswith('-') or '\n' in text or '\r' in text or len(text) > 32:
        raise ValidationError(message('badSsid'))
    return text


def wifi_password(value: str, required: bool) -> str:
    text = value or ''
    if '\n' in text or '\r' in text:
        raise ValidationError(message('passwordBreak'))
    if required and not text.strip():
        raise ValidationError(message('needPassword'))
    return text


_SYSTEM_USER = re.compile(r'^[a-z_][a-z0-9_-]{0,30}$')
_DNS_LABEL = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$')
PASSWORD_MIN = 6
PASSWORD_MAX = 64


def port_number(value: str, field: str) -> int:
    text = (value or '').strip()
    if not text.isdigit() or not 1 <= int(text) <= 65535:
        raise ValidationError(message('badPort', field=field, value=text or message('empty')))
    return int(text)


def system_user(value: str) -> str:
    text = (value or '').strip()
    if not _SYSTEM_USER.match(text) or text == 'root':
        raise ValidationError(message('badUser', value=text or message('empty')))
    return text


def temporary_password(value: str) -> str:
    text = value or ''
    if (not PASSWORD_MIN <= len(text) <= PASSWORD_MAX or any(ch in text for ch in '\r\n\0')
            or text != text.strip()):
        raise ValidationError(message('badTempPassword', minimum=PASSWORD_MIN, maximum=PASSWORD_MAX))
    return text


def dns_name(value: str) -> str:
    text = (value or '').strip().rstrip('.').lower()
    labels = text.split('.')
    if not text or len(text) > 253 or not all(_DNS_LABEL.match(label) for label in labels):
        raise ValidationError(message('badDnsName', value=text or message('empty')))
    return text


def integer_between(value: str, minimum: int, maximum: int, field: str) -> int:
    text = (value or '').strip()
    if not text.isdigit() or not minimum <= int(text) <= maximum:
        raise ValidationError(message('outOfRange', field=field, minimum=minimum, maximum=maximum))
    return int(text)


def ping_request(target: str, count: float, interval: float, size: float) -> PingRequest:
    return PingRequest(
        target=host(target),
        count=int(_in_range(int(count), PING_COUNT, 'Envios')),
        interval=_in_range(round(float(interval), 2), PING_INTERVAL, 'Intervalo'),
        size=int(_in_range(int(size), PING_SIZE, 'Tamaño')))
