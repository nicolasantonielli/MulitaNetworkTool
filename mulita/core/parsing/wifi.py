"""Parsers for wifi data."""
from __future__ import annotations

import ipaddress
import json
import re
from typing import NamedTuple
from mulita.core.errors import CommandFailedError
from mulita.core.models import EthernetConfig, WifiLink, WifiNetwork
from .network import parse_default_gateway, parse_nmcli_device_ipv4


def parse_saved_wifi(text: str) -> list[dict[str, str]]:
    profiles = []
    for line in text.splitlines():
        parts = ['']
        escaped = False
        for char in line:
            if escaped:
                parts[-1] += char
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == ':':
                parts.append('')
            else:
                parts[-1] += char
        if len(parts) == 3 and parts[0] and parts[2] in ('802-11-wireless', 'wifi'):
            profiles.append({'uuid': parts[0], 'name': parts[1]})
    return sorted(profiles, key=lambda item: (item['name'].casefold(), item['uuid']))


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
        parts.append('short GI')
    elif re.search(r'long GI', line or '', re.IGNORECASE):
        parts.append('long GI')
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


_UNSIGNED = re.compile(r'(\d+)')
_SIGNED = re.compile(r'(-?\d+)')
_IW_CHANNEL = re.compile(
    r'channel\s+(\d+)\s+\((\d+)\s*MHz\)(?:,\s*width:\s*([^,]+))?(?:,\s*center1:\s*(\d+)\s*MHz)?',
    re.IGNORECASE)
_IW_ADDR = re.compile(r'^\s*addr\s+([0-9a-f:]{17})', re.IGNORECASE | re.MULTILINE)
_IW_TYPE = re.compile(r'^\s*type\s+(.+)$', re.IGNORECASE | re.MULTILINE)
_IW_SSID = re.compile(r'^\s*ssid\s+(.+)$', re.IGNORECASE | re.MULTILINE)
_IW_POWER = re.compile(r'^\s*txpower\s+(-?\d+(?:\.\d+)?)\s*dBm', re.IGNORECASE | re.MULTILINE)


class _IpSettings(NamedTuple):
    address: str
    netmask: str
    gateway: str
    dns: str
    ipv6: str
    mac: str


class _IwInfo(NamedTuple):
    mac: str
    mode: str
    ssid: str
    power: str
    channel: str
    frequency: int | None
    width: str
    center: str


def _number(pattern: re.Pattern, text: str) -> int | None:
    match = pattern.search(text)
    return int(match.group(1)) if match else None


def _ip_settings(addr: str, route: str, lease: str) -> _IpSettings:
    """IPv4, mascara, puerta de enlace, DNS e IPv6. Si `ip` o `nmcli` fallan, lo que falte queda vacio."""
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
    netmask = f'{ipaddress.IPv4Network(f"0.0.0.0/{prefix}").netmask} (/{prefix})' if address else ''
    return _IpSettings(address, netmask, gateway or reported.gateway, reported.dns, ipv6, mac)


def _iw_info(text: str) -> _IwInfo:
    """Lo que informa `iw dev <interfaz> info`."""
    text = text or ''
    channel = _IW_CHANNEL.search(text)
    addr, kind, ssid, power = (pattern.search(text) for pattern in (_IW_ADDR, _IW_TYPE, _IW_SSID, _IW_POWER))
    return _IwInfo(
        mac=addr.group(1) if addr else '',
        mode=kind.group(1).strip() if kind else '',
        ssid=ssid.group(1).strip() if ssid else '',
        power=f'{float(power.group(1)):g} dBm' if power else '',
        channel=channel.group(1) if channel else '',
        frequency=int(channel.group(2)) if channel else None,
        width=channel.group(3).strip() if channel and channel.group(3) else '',
        center=f'{channel.group(4)} MHz' if channel and channel.group(4) else '')


def _frequency_and_channel(link: dict, radio: dict, info: _IwInfo) -> tuple[int | None, str]:
    freq = _mhz(link.get('freq', '')) or info.frequency or _mhz(radio.get('frequency', ''))
    if info.channel:
        return freq, info.channel
    if radio.get('channel', '').isdigit():
        return freq, radio['channel']
    return freq, _channel(freq) if freq else ''


def _rates(link: dict, sta: dict, radio: dict) -> tuple[str, str, str, str]:
    """Velocidad y MCS de recepcion y de transmision."""
    rate_rx, mcs_rx = _bitrate(link.get('rx bitrate', '') or sta.get('rx bitrate', ''))
    rate_tx, mcs_tx = _bitrate(link.get('tx bitrate', '') or sta.get('tx bitrate', ''))
    if not rate_rx and not rate_tx and radio.get('rate'):
        rate_rx = radio['rate']
    return rate_rx, mcs_rx, rate_tx, mcs_tx


def _signal(link: dict, sta: dict, radio: dict, active: WifiNetwork | None) -> tuple[str, int | None]:
    """Texto de la senal (dBm, promedio y porcentaje) y los dBm medidos."""
    if active and active.signal:
        percent = f'{active.signal} %'
    elif radio.get('signal', '').isdigit():
        percent = f'{radio["signal"]} %'
    else:
        percent = ''
    dbm = _number(_SIGNED, sta.get('signal', '') or link.get('signal', ''))
    if dbm is None:
        return percent, None
    signal = f'{dbm} dBm'
    average = _number(_SIGNED, sta.get('signal avg', ''))
    if average is not None and average != dbm:
        signal += f' · avg {average} dBm'
    if percent:
        signal += f' · {percent}'
    return signal, dbm


def build_wifi_link(interface: str, addr: str, route: str, lease: str, details: str,
                    iw_link: str, iw_info: str, station: str, survey: str,
                    networks: tuple[WifiNetwork, ...] = ()) -> WifiLink:
    """Junta IP, nmcli e iw. Lo que falta queda vacío y no se muestra."""
    ip = _ip_settings(addr, route, lease)
    active = next((item for item in networks if item.active), None)
    radio = parse_wifi_active(details)
    link, sta = _lines(iw_link), _lines(station)
    info = _iw_info(iw_info)
    connected = _CONNECTED.search(iw_link or '')
    freq, channel = _frequency_and_channel(link, radio, info)
    rate_rx, mcs_rx, rate_tx, mcs_tx = _rates(link, sta, radio)
    signal, dbm = _signal(link, sta, radio, active)
    noise = _survey_noise(survey, freq)
    noise_dbm = _number(_SIGNED, noise)
    uptime = _number(_UNSIGNED, sta.get('connected time', ''))
    received = _number(_UNSIGNED, link.get('rx', ''))
    sent = _number(_UNSIGNED, link.get('tx', ''))
    return WifiLink(
        interface=interface,
        ssid=link.get('ssid') or (active.ssid if active else '') or info.ssid,
        bssid=(connected.group(1) if connected else radio.get('bssid', '')).lower(),
        security=(active.security if active and active.security else '') or radio.get('security', ''),
        mode=info.mode,
        mac=(info.mac or ip.mac).lower(),
        address=ip.address,
        netmask=ip.netmask,
        gateway=ip.gateway,
        dns=ip.dns,
        ipv6=ip.ipv6,
        band=_band(freq) if freq else '',
        channel=channel,
        frequency=f'{freq} MHz' if freq else '',
        width=info.width,
        center=info.center,
        signal=signal,
        noise=noise,
        snr=f'{dbm - noise_dbm} dB' if dbm is not None and noise_dbm is not None else '',
        mcs_rx=mcs_rx,
        mcs_tx=mcs_tx,
        rate_rx=rate_rx,
        rate_tx=rate_tx,
        tx_power=info.power,
        uptime=_duration(uptime) if uptime is not None else '',
        beacon=f'{link["beacon int"]} TU' if link.get('beacon int', '').isdigit() else '',
        dtim=link.get('dtim period', ''),
        retries=sta.get('tx retries', ''),
        failed=sta.get('tx failed', ''),
        beacon_loss=sta.get('beacon loss', ''),
        rx=_size(received) if received is not None else '',
        tx=_size(sent) if sent is not None else '',
    )
