"""Parsers for network data."""
from __future__ import annotations

import ipaddress
import json
import re
from mulita.core.errors import CommandFailedError
from mulita.core.models import AddressMode, EthernetConfig, NetworkInterface


def cable_connected(name: str, flags: list, operstate: str) -> bool:
    """Ethernet administrativamente arriba y con cable. Wi-Fi y loopback no cuentan."""
    if name == 'lo' or name.startswith(('wlan', 'wlp', 'wlx', 'wifi')):
        return False
    present = {str(flag).upper() for flag in flags or []}
    state = (operstate or '').upper()
    if 'NO-CARRIER' in present or state in ('DOWN', 'LOWERLAYERDOWN'):
        return False
    admin_up = 'UP' in present
    carrier = 'LOWER_UP' in present or 'RUNNING' in present or state == 'UP'
    return admin_up and carrier


def parse_interfaces(text: str) -> list[NetworkInterface]:
    """Salida de `ip -j addr`."""
    try:
        data = json.loads(text or '[]')
    except json.JSONDecodeError as exc:
        raise CommandFailedError(f'Respuesta de ip invalida: {exc}') from exc

    interfaces = []
    for item in data:
        name = item.get('ifname')
        if not name:
            continue
        addresses = tuple(info['local'] for info in item.get('addr_info', []) if 'local' in info)
        interfaces.append(NetworkInterface(
            name=name,
            mac=item.get('address'),
            addresses=addresses,
            cable=cable_connected(name, item.get('flags') or [], item.get('operstate') or '')))
    return interfaces


def parse_connection_name(text: str) -> str | None:
    """`nmcli -g GENERAL.CONNECTION device show`. Vacio o `--` si no hay conexion."""
    name = (text or '').strip()
    if not name or name == '--':
        return None
    return name


_IPV4 = re.compile(r'(\d{1,3}(?:\.\d{1,3}){3})(?:/(\d{1,2}))?')


_NMCLI_FIELD = re.compile(
    r'(IP4\.(?:ADDRESS|GATEWAY|DNS))(?:\[\d+\])?\s*[:=]\s*([^:\n]*)',
    re.IGNORECASE)


def _ipv4(value: str) -> tuple[str, int | None]:
    match = _IPV4.search(value or '')
    if not match:
        return '', None
    prefix = int(match.group(2)) if match.group(2) else None
    return match.group(1), prefix


def parse_nmcli_device_ipv4(text: str) -> EthernetConfig:
    """DNS y, si vienen, IP y gateway de `nmcli device show`."""
    address = ''
    prefix = 24
    gateway = ''
    dns: list[str] = []
    for match in _NMCLI_FIELD.finditer(text or ''):
        key = match.group(1).upper()
        value = match.group(2).replace('\\:', ':').strip()
        if key == 'IP4.ADDRESS' and not address:
            found, length = _ipv4(value)
            if found:
                address = found
                if length is not None:
                    prefix = length
            if not gateway:
                route = re.search(r'gw\s*=\s*(\d{1,3}(?:\.\d{1,3}){3})', value)
                if route:
                    gateway = route.group(1)
        elif key == 'IP4.GATEWAY' and not gateway:
            found, _length = _ipv4(value)
            gateway = found
        elif key == 'IP4.DNS':
            found, _length = _ipv4(value)
            if found:
                dns.append(found)
    return EthernetConfig(AddressMode.DHCP, address, prefix, gateway, ', '.join(dns))


def interface_network(text: str, name: str) -> str:
    """Red IPv4 de una interfaz en `ip -j addr`, como 192.168.0.0/24."""
    try:
        data = json.loads(text or '[]')
    except json.JSONDecodeError as exc:
        raise CommandFailedError(f'Respuesta de ip invalida: {exc}') from exc
    for item in data:
        if item.get('ifname') != name:
            continue
        for info in item.get('addr_info', []):
            if info.get('family') != 'inet':
                continue
            local = str(info.get('local') or '')
            try:
                address = ipaddress.IPv4Address(local)
            except ValueError:
                continue
            if address.is_loopback or address.is_link_local or address.is_unspecified:
                continue
            try:
                prefix = int(info.get('prefixlen', 24))
            except (TypeError, ValueError):
                prefix = 24
            if not 0 <= prefix <= 32:
                prefix = 24
            return str(ipaddress.IPv4Network(f'{address}/{prefix}', strict=False))
    return ''


def parse_interface_ipv4(text: str) -> tuple[str, int]:
    """Primera IPv4 global de `ip -j addr show dev <if>`."""
    try:
        data = json.loads(text or '[]')
    except json.JSONDecodeError as exc:
        raise CommandFailedError(f'Respuesta de ip invalida: {exc}') from exc
    for item in data:
        for info in item.get('addr_info', []):
            if info.get('family') != 'inet':
                continue
            local = str(info.get('local') or '')
            if not local or local.startswith('127.'):
                continue
            try:
                prefix = int(info.get('prefixlen', 24))
            except (TypeError, ValueError) as exc:
                raise CommandFailedError(f'Prefijo de red invalido: {info.get("prefixlen")}') from exc
            return local, prefix
    return '', 24


def parse_default_gateway(text: str) -> str:
    """Gateway de `ip -j route show default`."""
    try:
        data = json.loads(text or '[]')
    except json.JSONDecodeError as exc:
        raise CommandFailedError(f'Respuesta de ip invalida: {exc}') from exc
    for route in data:
        if route.get('dst') not in ('default', '0.0.0.0/0'):
            continue
        gateway = str(route.get('gateway') or '')
        if gateway:
            return gateway
    return ''


def parse_nmcli_ipv4(text: str) -> EthernetConfig:
    """Cuatro lineas de `nmcli -g ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns`."""
    lines = (text or '').splitlines()
    lines += [''] * (4 - len(lines))
    method, addresses, gateway, dns = (line.strip() for line in lines[:4])
    if method != 'manual':
        return EthernetConfig(AddressMode.DHCP)
    first = addresses.split('|')[0].strip()
    gateway = gateway.split('|')[0].strip()
    dns = dns.split('|')[0].strip()
    if '/' not in first:
        return EthernetConfig(AddressMode.ESTATICA, first, 24, gateway, dns)
    address, prefix = first.split('/', 1)
    try:
        length = int(prefix)
    except ValueError as exc:
        raise CommandFailedError(f'Prefijo de red invalido: {prefix}') from exc
    return EthernetConfig(AddressMode.ESTATICA, address, length, gateway, dns)
