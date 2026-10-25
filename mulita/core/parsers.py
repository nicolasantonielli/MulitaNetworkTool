from __future__ import annotations

import json

from mulita.core.errors import CommandFailedError
from mulita.core.models import AddressMode, EthernetConfig, NetworkInterface, SpeedTestResult


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
        interfaces.append(NetworkInterface(name=name, mac=item.get('address'), addresses=addresses))
    return interfaces


def parse_connection_name(text: str) -> str | None:
    """`nmcli -g GENERAL.CONNECTION device show`. Vacio o `--` si no hay conexion."""
    name = (text or '').strip()
    if not name or name == '--':
        return None
    return name


def parse_nmcli_device_ipv4(text: str) -> EthernetConfig:
    """Lo que la interfaz tiene ahora: `nmcli -t -f IP4.ADDRESS,IP4.GATEWAY,IP4.DNS device show`."""
    address = ''
    prefix = 24
    gateway = ''
    dns: list[str] = []
    for raw in (text or '').splitlines():
        line = raw.strip()
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        value = value.replace('\\:', ':').strip()
        key = key.split('[', 1)[0]
        if key == 'IP4.ADDRESS' and not address and '/' in value:
            ip, length = value.split('/', 1)
            try:
                prefix = int(length)
            except ValueError as exc:
                raise CommandFailedError(f'Prefijo de red invalido: {length}') from exc
            address = ip
        elif key == 'IP4.GATEWAY' and value and not gateway:
            gateway = value
        elif key == 'IP4.DNS' and value:
            dns.append(value)
    return EthernetConfig(AddressMode.DHCP, address, prefix, gateway, ', '.join(dns))


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


def parse_speed_test(text: str) -> SpeedTestResult:
    """Salida de `speedtest --json` (speedtest-cli), en bits por segundo."""
    try:
        data = json.loads(text)
        return SpeedTestResult(download_bps=float(data['download']), upload_bps=float(data['upload']))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise CommandFailedError('No se pudo interpretar el resultado del test de velocidad') from exc
