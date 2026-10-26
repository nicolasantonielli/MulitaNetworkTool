from __future__ import annotations

import csv
import io
import ipaddress
import json
import re

from mulita.core.errors import CommandFailedError
from mulita.presentation.i18n import tr
from mulita.core.models import (AddressMode, EthernetConfig, NetworkInterface,
                                PingReply, PingSummary, PublicAddress, SpeedTestResult,
                                TraceHop, WifiLink, WifiNetwork)


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
    'managed': 'wifiModeInfra',
    'AP': 'wifiModeAp',
    'monitor': 'wifiModeMonitor',
    'mesh point': 'wifiModeMesh',
    'IBSS': 'wifiModeAdhoc',
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
        parts.append(tr('wifiShortGi'))
    elif re.search(r'long GI', line or '', re.IGNORECASE):
        parts.append(tr('wifiLongGi'))
    else:
        gi = _HE_GI.search(line or '')
        if gi:
            parts.append(f'GI {_GI_US.get(gi.group(1), gi.group(1))}')
    return rate, ' · '.join(parts)


def _duration(seconds: int) -> str:
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return tr('durationHours', hours=hours, minutes=minutes)
    if minutes:
        return tr('durationMinutes', minutes=minutes, sec=sec)
    return tr('durationSeconds', sec=sec)


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
            signal += tr('signalAvg', value=avg_match.group(1))
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
    mode = tr(_MODE[kind_name]) if kind_name in _MODE else kind_name
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
        raise CommandFailedError(tr('vendorFail'))
    try:
        status = int(code.strip())
    except ValueError as exc:
        raise CommandFailedError(tr('vendorFail')) from exc
    name = body.strip()
    if status == 200 and name:
        return name
    if status == 404:
        raise CommandFailedError(tr('vendorMiss'))
    if status == 429:
        raise CommandFailedError(tr('vendorLimit'))
    raise CommandFailedError(tr('vendorStatus', status=status))


_TRACE_HOP = re.compile(
    r'^\s*(?P<hop>\d+)\.\s*(?:\|--\s*)?(?P<address>\S+)\s+'
    r'(?P<loss>\d+(?:\.\d+)?)%?\s+'
    r'(?P<sent>\d+)\s+'
    r'(?P<last>\S+)\s+(?P<average>\S+)\s+(?P<best>\S+)\s+'
    r'(?P<worst>\S+)\s+(?P<deviation>\S+)\s*$')


def parse_trace(text: str) -> tuple[TraceHop, ...]:
    """Informe de mtr, en CSV o en el cuadro de texto del reporte."""
    if 'Mtr_Version' in (text or ''):
        return _parse_trace_csv(text)
    return _parse_trace_report(text)


def _parse_trace_csv(text: str) -> tuple[TraceHop, ...]:
    rows = list(csv.reader(io.StringIO(text or '')))
    header_at = next((index for index, row in enumerate(rows)
                      if row and row[0].strip() == 'Mtr_Version'), None)
    if header_at is None:
        return ()
    header = [cell.strip().lower() for cell in rows[header_at]]
    hop_at = _trace_column(header, 'hop')
    address_at = _trace_column(header, 'ip')
    if hop_at is None or address_at is None:
        return ()
    loss_at = _trace_column(header, 'loss%', 'loss')
    sent_at = _trace_column(header, 'snt')
    last_at = _trace_column(header, 'last')
    average_at = _trace_column(header, 'avg')
    best_at = _trace_column(header, 'best')
    worst_at = _trace_column(header, 'wrst', 'worst')
    deviation_at = _trace_column(header, 'stdev', 'jitter')
    hops: list[TraceHop] = []
    for row in rows[header_at + 1:]:
        if not row or row[0].strip() == 'Mtr_Version':
            continue
        hop = _trace_cell(row, hop_at)
        if not hop.isdigit():
            continue
        hops.append(TraceHop(
            hop=int(hop),
            address=_trace_cell(row, address_at) or '???',
            loss=_trace_loss(_trace_cell(row, loss_at)),
            sent=_trace_cell(row, sent_at),
            last=_trace_cell(row, last_at),
            average=_trace_cell(row, average_at),
            best=_trace_cell(row, best_at),
            worst=_trace_cell(row, worst_at),
            deviation=_trace_cell(row, deviation_at),
        ))
    return tuple(hops)


def _parse_trace_report(text: str) -> tuple[TraceHop, ...]:
    hops: list[TraceHop] = []
    for line in (text or '').splitlines():
        match = _TRACE_HOP.match(line)
        if not match:
            continue
        hops.append(TraceHop(
            hop=int(match.group('hop')),
            address=match.group('address'),
            loss=_trace_loss(match.group('loss')),
            sent=match.group('sent'),
            last=match.group('last'),
            average=match.group('average'),
            best=match.group('best'),
            worst=match.group('worst'),
            deviation=match.group('deviation'),
        ))
    return tuple(hops)


def _trace_column(header: list[str], *names: str) -> int | None:
    for name in names:
        if name in header:
            return header.index(name)
    return None


def _trace_cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ''
    return row[index].strip()


def _trace_loss(value: str) -> str:
    text = (value or '').strip()
    if not text or text.endswith('%'):
        return text
    return text + '%'


_PING_REPLY = re.compile(
    r'^(?P<size>\d+)\s+bytes from\s+(?P<source>.+?):\s+'
    r'(?:icmp_)?seq=(?P<seq>\d+)\s+ttl=(?P<ttl>\d+)\s+time=(?P<time>[\d.]+)\s*ms'
    r'(?P<extra>.*)$', re.IGNORECASE)
_PING_FAIL = re.compile(
    r'^From\s+(?P<source>\S+?):?\s+(?:icmp_)?seq=(?P<seq>\d+)\s+(?P<status>.+)$',
    re.IGNORECASE)
_PING_TARGET = re.compile(r'^---\s+(?P<target>.+?)\s+ping statistics\s+---\s*$', re.IGNORECASE)
_PING_LOSS = re.compile(
    r'(?P<tx>\d+)\s+packets transmitted,\s+(?P<rx>\d+)\s+(?:packets\s+)?received,\s+'
    r'(?:\+(?P<errors>\d+)\s+errors,\s+)?'
    r'(?P<loss>[\d.]+)%\s+packet loss(?:,\s+time\s+(?P<elapsed>\d+)ms)?',
    re.IGNORECASE)
_PING_RTT = re.compile(
    r'(?:rtt|round-trip)\s+min/avg/max(?:/mdev)?\s*=\s*'
    r'(?P<min>[\d.]+)/(?P<avg>[\d.]+)/(?P<max>[\d.]+)(?:/(?P<mdev>[\d.]+))?\s*ms',
    re.IGNORECASE)


def read_ping_line(line: str, summary: PingSummary | None = None) -> tuple[PingReply | None, PingSummary]:
    """Una linea de ping de Linux. Devuelve la respuesta, si hay, y el resumen acumulado."""
    current = summary or PingSummary()
    text = (line or '').strip()
    target = _PING_TARGET.match(text)
    if target:
        return None, _copy_summary(current, target=target.group('target'))
    loss = _PING_LOSS.search(text)
    if loss:
        return None, _copy_summary(
            current,
            transmitted=loss.group('tx'),
            received=loss.group('rx'),
            loss=f"{loss.group('loss')}%",
            elapsed=f"{loss.group('elapsed')} ms" if loss.group('elapsed') else current.elapsed,
        )
    rtt = _PING_RTT.search(text)
    if rtt:
        return None, _copy_summary(
            current,
            minimum=rtt.group('min'),
            average=rtt.group('avg'),
            maximum=rtt.group('max'),
            deviation=rtt.group('mdev') or current.deviation,
        )
    reply = _PING_REPLY.match(text)
    if reply:
        extra = reply.group('extra') or ''
        status = 'dup' if 'DUP!' in extra.upper() else 'ok'
        return PingReply(
            seq=int(reply.group('seq')),
            source=reply.group('source').strip(),
            ttl=reply.group('ttl'),
            time=reply.group('time'),
            status=status,
        ), current
    failed = _PING_FAIL.match(text)
    if failed:
        return PingReply(
            seq=int(failed.group('seq')),
            source=failed.group('source').strip(),
            ttl='',
            time='',
            status='fail',
            detail=failed.group('status').strip(),
        ), current
    return None, current


def _copy_summary(summary: PingSummary, **changes: str) -> PingSummary:
    data = {
        'target': summary.target,
        'transmitted': summary.transmitted,
        'received': summary.received,
        'loss': summary.loss,
        'elapsed': summary.elapsed,
        'minimum': summary.minimum,
        'average': summary.average,
        'maximum': summary.maximum,
        'deviation': summary.deviation,
    }
    data.update({key: value for key, value in changes.items() if value})
    return PingSummary(**data)


def parse_public_address(text: str) -> PublicAddress:
    """JSON de ipwho.is, o una sola linea con la direccion."""
    body = (text or '').strip()
    if not body:
        raise CommandFailedError(tr('pubFail'))
    if not body.startswith('{'):
        address = body.splitlines()[0].strip()
        if not _ip_text(address):
            raise CommandFailedError(tr('pubFail'))
        return PublicAddress(ip=address, version=_ip_version(address))
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise CommandFailedError(tr('pubFail')) from exc
    if not isinstance(data, dict) or data.get('success') is False or not data.get('ip'):
        raise CommandFailedError(tr('pubFail'))
    connection = data.get('connection') if isinstance(data.get('connection'), dict) else {}
    zone = data.get('timezone') if isinstance(data.get('timezone'), dict) else {}
    asn = connection.get('asn')
    asn_text = f'AS{asn}' if isinstance(asn, int) or (isinstance(asn, str) and asn.isdigit()) else _text(asn)
    country = _text(data.get('country'))
    code = _text(data.get('country_code'))
    if country and code:
        country = f'{country} ({code})'
    utc = _text(zone.get('utc'))
    zone_id = _text(zone.get('id'))
    if zone_id and utc:
        zone_id = f'{zone_id} (UTC{utc})'
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    coordinates = ''
    if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
        coordinates = f'{latitude:.4f}, {longitude:.4f}'
    address = _text(data.get('ip'))
    return PublicAddress(
        ip=address,
        version=_text(data.get('type')) or _ip_version(address),
        asn=asn_text,
        organization=_text(connection.get('org')),
        isp=_text(connection.get('isp')),
        domain=_text(connection.get('domain')),
        country=country,
        region=_text(data.get('region')),
        city=_text(data.get('city')),
        coordinates=coordinates,
        timezone=zone_id,
    )


def _text(value) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _ip_text(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _ip_version(value: str) -> str:
    try:
        return f'IPv{ipaddress.ip_address(value).version}'
    except ValueError:
        return ''


def parse_speed_test(text: str) -> SpeedTestResult:
    """Salida de `speedtest --json` (speedtest-cli), en bits por segundo."""
    try:
        data = json.loads(text)
        return SpeedTestResult(download_bps=float(data['download']), upload_bps=float(data['upload']))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise CommandFailedError('No se pudo interpretar el resultado del test de velocidad') from exc
