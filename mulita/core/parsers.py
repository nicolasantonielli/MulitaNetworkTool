from __future__ import annotations

import ipaddress
import json
import re

from mulita.core.errors import CommandFailedError
from mulita.core.models import (AddressMode, EthernetConfig, NetworkInterface,
                                SpeedTestResult, WifiLink, WifiNetwork)


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


def _nmcli_columns(line: str) -> list[str]:
    escaped = line.replace('\\:', '\x00')
    return [part.replace('\x00', ':') for part in escaped.split(':')]


def parse_wifi_device(text: str) -> str | None:
    """Primera interfaz wifi de `nmcli -t -f DEVICE,TYPE device status`."""
    for raw in (text or '').splitlines():
        parts = _nmcli_columns(raw.strip())
        if len(parts) < 2:
            continue
        device, kind = parts[0].strip(), parts[1].strip()
        if kind == 'wifi' and device and not device.startswith('p2p'):
            return device
    return None


def parse_wifi_list(text: str) -> list[WifiNetwork]:
    """`nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list`."""
    found: dict[str, WifiNetwork] = {}
    for raw in (text or '').splitlines():
        parts = _nmcli_columns(raw.strip())
        if len(parts) < 4:
            continue
        in_use, ssid, signal = parts[0].strip(), parts[1].strip(), parts[2].strip()
        security = ':'.join(parts[3:]).strip()
        if not ssid:
            continue
        try:
            strength = int(signal)
        except ValueError:
            strength = 0
        network = WifiNetwork(
            ssid=ssid,
            signal=max(0, min(100, strength)),
            security='' if security in ('', '--') else security,
            active=in_use == '*')
        previous = found.get(ssid)
        if previous is None or network.active or network.signal > previous.signal:
            found[ssid] = network
    return sorted(found.values(), key=lambda item: (not item.active, -item.signal, item.ssid.lower()))


def parse_wifi_active(text: str) -> dict[str, str]:
    """Fila en uso de `nmcli -t -f IN-USE,BSSID,CHAN,FREQ,RATE,SIGNAL,SECURITY`."""
    for raw in (text or '').splitlines():
        parts = _nmcli_columns(raw.strip())
        if not parts or parts[0].strip() != '*':
            continue
        parts += [''] * (7 - len(parts))
        security = ':'.join(parts[6:]).strip()
        return {
            'bssid': parts[1].strip(),
            'channel': parts[2].strip(),
            'frequency': parts[3].strip(),
            'rate': parts[4].strip(),
            'signal': parts[5].strip(),
            'security': '' if security in ('', '--') else security,
        }
    return {}


def parse_interface_details(text: str) -> tuple[str, int, str, str]:
    """IPv4, prefijo, MAC e IPv6 de `ip -j addr show dev`."""
    try:
        data = json.loads(text or '[]')
    except json.JSONDecodeError as exc:
        raise CommandFailedError(f'Respuesta de ip invalida: {exc}') from exc
    address, prefix, mac, ipv6 = '', 24, '', []
    for item in data:
        mac = mac or str(item.get('address') or '')
        for info in item.get('addr_info', []):
            local = str(info.get('local') or '')
            if info.get('family') == 'inet' and local and not local.startswith('127.') and not address:
                address = local
                try:
                    prefix = int(info.get('prefixlen', 24))
                except (TypeError, ValueError) as exc:
                    raise CommandFailedError(f'Prefijo de red invalido: {info.get("prefixlen")}') from exc
            elif info.get('family') == 'inet6' and local:
                ipv6.append(local)
    return address, prefix, mac, ', '.join(ipv6)


_CONNECTED = re.compile(r'Connected to\s+([0-9a-f:]{17})', re.IGNORECASE)
_FIELD = re.compile(r'^\s*([A-Za-z][A-Za-z0-9 /_-]*?):\s*(.*?)\s*$', re.MULTILINE)
_MCS = re.compile(r'((?:EHT|HE|VHT)-MCS|MCS)\s+(\d+)', re.IGNORECASE)
_NSS = re.compile(r'(?:EHT-|HE-|VHT-)?NSS\s+(\d+)', re.IGNORECASE)
_WIDTH = re.compile(r'(\d+)\s*MHz', re.IGNORECASE)
_HE_GI = re.compile(r'(?:HE|EHT)-GI\s+(\d+)', re.IGNORECASE)
_GI_US = {'0': '0.8 µs', '1': '1.6 µs', '2': '3.2 µs'}
_MODE = {
    'managed': 'Infraestructura',
    'AP': 'Punto de acceso',
    'monitor': 'Monitor',
    'mesh point': 'Mesh',
    'IBSS': 'Ad hoc',
}


def _lines(text: str) -> dict[str, str]:
    found = {}
    for match in _FIELD.finditer(text or ''):
        found.setdefault(match.group(1).strip().lower(), match.group(2).strip())
    return found


def _band(freq: int) -> str:
    if 2400 <= freq < 2500:
        return '2.4 GHz'
    if 5000 <= freq < 5925:
        return '5 GHz'
    if 5925 <= freq <= 7125:
        return '6 GHz'
    return ''


def _channel(freq: int) -> str:
    if freq == 2484:
        return '14'
    if 2412 <= freq <= 2472 and (freq - 2412) % 5 == 0:
        return str(1 + (freq - 2412) // 5)
    if 5000 <= freq <= 5900 and freq % 5 == 0:
        return str((freq - 5000) // 5)
    if 5955 <= freq <= 7115 and (freq - 5955) % 5 == 0:
        return str((freq - 5950) // 5)
    return ''


def _mhz(value: str) -> int | None:
    match = re.search(r'(\d+)', value or '')
    if not match:
        return None
    freq = int(match.group(1))
    return freq if freq >= 2000 else None


def _bitrate(line: str) -> tuple[str, str]:
    """Velocidad y descripción MCS de una línea `rx bitrate` / `tx bitrate`."""
    rate_match = re.search(r'(\d+(?:\.\d+)?)\s*MBit/s', line or '', re.IGNORECASE)
    rate = f'{rate_match.group(1)} Mbit/s' if rate_match else ''
    parts = []
    mcs = _MCS.search(line or '')
    if mcs:
        kind = mcs.group(1).upper()
        parts.append(f'{kind} {mcs.group(2)}' if kind != 'MCS' else f'MCS {mcs.group(2)}')
    nss = _NSS.search(line or '')
    if nss:
        parts.append(f'NSS {nss.group(1)}')
    width = _WIDTH.search(line or '')
    if width:
        parts.append(f'{width.group(1)} MHz')
    if re.search(r'short GI', line or '', re.IGNORECASE):
        parts.append('GI corto')
    elif re.search(r'long GI', line or '', re.IGNORECASE):
        parts.append('GI largo')
    else:
        gi = _HE_GI.search(line or '')
        if gi:
            parts.append(f'GI {_GI_US.get(gi.group(1), gi.group(1))}')
    return rate, ' · '.join(parts)


def _duration(seconds: int) -> str:
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f'{hours} h {minutes} min'
    if minutes:
        return f'{minutes} min {sec} s'
    return f'{sec} s'


def _size(amount: int) -> str:
    value = float(amount)
    for unit in ('B', 'KiB', 'MiB', 'GiB'):
        if value < 1024 or unit == 'GiB':
            if unit == 'B':
                return f'{int(value)} B'
            text = f'{value:.1f}'.rstrip('0').rstrip('.')
            return f'{text} {unit}'
        value /= 1024
    return f'{amount} B'


def _survey_noise(text: str, freq: int | None) -> str:
    current = None
    noise = ''
    for raw in (text or '').splitlines():
        line = raw.strip().lower()
        if line.startswith('frequency:'):
            mhz = _mhz(line)
            current = mhz
            if '[in use]' in line and mhz:
                freq = mhz
            continue
        if line.startswith('noise:') and current and (freq is None or current == freq):
            match = re.search(r'(-?\d+)\s*dbm', line)
            if match:
                noise = f'{match.group(1)} dBm'
                if freq is not None and current == freq:
                    return noise
    return noise


def build_wifi_link(interface: str, addr: str, route: str, lease: str, details: str,
                    iw_link: str, iw_info: str, station: str, survey: str,
                    networks: tuple[WifiNetwork, ...] = ()) -> WifiLink:
    """Junta IP, nmcli e iw. Lo que falta queda vacío y no se muestra."""
    try:
        address, prefix, mac, ipv6 = parse_interface_details(addr)
    except CommandFailedError:
        address, prefix, mac, ipv6 = '', 24, '', ''
    try:
        gateway = parse_default_gateway(route)
    except CommandFailedError:
        gateway = ''
    try:
        reported = parse_nmcli_device_ipv4(lease)
    except CommandFailedError:
        reported = EthernetConfig()
    if not address:
        address, prefix = reported.address, reported.prefix
    if not gateway:
        gateway = reported.gateway
    netmask = ''
    if address:
        netmask = f'{ipaddress.IPv4Network(f"0.0.0.0/{prefix}").netmask} (/{prefix})'

    active = next((item for item in networks if item.active), None)
    radio = parse_wifi_active(details)
    link = _lines(iw_link)
    sta = _lines(station)
    connected = _CONNECTED.search(iw_link or '')
    bssid = (connected.group(1) if connected else radio.get('bssid', '')).lower()
    channel_line = re.search(
        r'channel\s+(\d+)\s+\((\d+)\s*MHz\)(?:,\s*width:\s*([^,]+))?(?:,\s*center1:\s*(\d+)\s*MHz)?',
        iw_info or '', re.IGNORECASE)
    addr = re.search(r'^\s*addr\s+([0-9a-f:]{17})', iw_info or '', re.IGNORECASE | re.MULTILINE)
    kind = re.search(r'^\s*type\s+(.+)$', iw_info or '', re.IGNORECASE | re.MULTILINE)
    info_ssid = re.search(r'^\s*ssid\s+(.+)$', iw_info or '', re.IGNORECASE | re.MULTILINE)
    power_match = re.search(r'^\s*txpower\s+(-?\d+(?:\.\d+)?)\s*dBm', iw_info or '', re.IGNORECASE | re.MULTILINE)
    freq = (_mhz(link.get('freq', ''))
             or (int(channel_line.group(2)) if channel_line else None)
             or _mhz(radio.get('frequency', '')))
    if channel_line:
        channel = channel_line.group(1)
    elif radio.get('channel', '').isdigit():
        channel = radio['channel']
    elif freq:
        channel = _channel(freq)
    else:
        channel = ''
    rate_rx, mcs_rx = _bitrate(link.get('rx bitrate', '') or sta.get('rx bitrate', ''))
    rate_tx, mcs_tx = _bitrate(link.get('tx bitrate', '') or sta.get('tx bitrate', ''))
    if not rate_rx and not rate_tx and radio.get('rate'):
        rate_rx = radio['rate']
    uptime_match = re.search(r'(\d+)', sta.get('connected time', ''))
    signal_match = re.search(r'(-?\d+)', sta.get('signal', '') or link.get('signal', ''))
    avg_match = re.search(r'(-?\d+)', sta.get('signal avg', ''))
    percent = ''
    if active and active.signal:
        percent = f'{active.signal} %'
    elif radio.get('signal', '').isdigit():
        percent = f'{radio["signal"]} %'
    signal = ''
    dbm = int(signal_match.group(1)) if signal_match else None
    if dbm is not None:
        signal = f'{dbm} dBm'
        if avg_match and int(avg_match.group(1)) != dbm:
            signal += f' · media {avg_match.group(1)} dBm'
        if percent:
            signal += f' · {percent}'
    elif percent:
        signal = percent
    noise = _survey_noise(survey, freq)
    snr = ''
    noise_match = re.search(r'(-?\d+)', noise)
    if dbm is not None and noise_match:
        snr = f'{dbm - int(noise_match.group(1))} dB'
    uptime = _duration(int(uptime_match.group(1))) if uptime_match else ''
    power = f'{float(power_match.group(1)):g} dBm' if power_match else ''
    rx = re.search(r'(\d+)', link.get('rx', ''))
    tx = re.search(r'(\d+)', link.get('tx', ''))
    kind_name = kind.group(1).strip() if kind else ''
    mode = _MODE.get(kind_name, kind_name)
    info_name = info_ssid.group(1).strip() if info_ssid else ''
    return WifiLink(
        interface=interface,
        ssid=link.get('ssid') or (active.ssid if active else '') or info_name,
        bssid=bssid,
        security=(active.security if active and active.security else '') or radio.get('security', ''),
        mode=mode,
        mac=((addr.group(1) if addr else '') or mac).lower(),
        address=address,
        netmask=netmask,
        gateway=gateway,
        dns=reported.dns,
        ipv6=ipv6,
        band=_band(freq) if freq else '',
        channel=channel,
        frequency=f'{freq} MHz' if freq else '',
        width=channel_line.group(3).strip() if channel_line and channel_line.group(3) else '',
        center=f'{channel_line.group(4)} MHz' if channel_line and channel_line.group(4) else '',
        signal=signal,
        noise=noise,
        snr=snr,
        mcs_rx=mcs_rx,
        mcs_tx=mcs_tx,
        rate_rx=rate_rx,
        rate_tx=rate_tx,
        tx_power=power,
        uptime=uptime,
        beacon=f'{link["beacon int"]} TU' if link.get('beacon int', '').isdigit() else '',
        dtim=link.get('dtim period', ''),
        retries=sta.get('tx retries', ''),
        failed=sta.get('tx failed', ''),
        beacon_loss=sta.get('beacon loss', ''),
        rx=_size(int(rx.group(1))) if rx else '',
        tx=_size(int(tx.group(1))) if tx else '',
    )


def parse_mac_vendor(text: str) -> str:
    """Cuerpo y codigo HTTP de `curl -w '\\n%{http_code}'` contra MACVendors."""
    body, separator, code = (text or '').rpartition('\n')
    if not separator:
        raise CommandFailedError('No se pudo consultar el fabricante')
    try:
        status = int(code.strip())
    except ValueError as exc:
        raise CommandFailedError('No se pudo consultar el fabricante') from exc
    name = body.strip()
    if status == 200 and name:
        return name
    if status == 404:
        raise CommandFailedError('No se encontro el fabricante de esa MAC')
    if status == 429:
        raise CommandFailedError('Demasiadas consultas. La API permite una por segundo y mil por dia.')
    raise CommandFailedError(f'No se pudo consultar el fabricante ({status})')


def parse_speed_test(text: str) -> SpeedTestResult:
    """Salida de `speedtest --json` (speedtest-cli), en bits por segundo."""
    try:
        data = json.loads(text)
        return SpeedTestResult(download_bps=float(data['download']), upload_bps=float(data['upload']))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise CommandFailedError('No se pudo interpretar el resultado del test de velocidad') from exc
