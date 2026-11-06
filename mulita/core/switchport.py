"""Lectura pasiva de anuncios LLDP/CDP y etiquetas Ethernet 802.1Q."""
from __future__ import annotations

import ipaddress
import struct


def _text(raw: bytes) -> str:
    return ''.join(c for c in raw.decode('utf-8', errors='replace') if c.isprintable())[:1024]


def _mac(raw: bytes) -> str:
    return ':'.join(f'{part:02x}' for part in raw)


def _address(raw: bytes) -> str:
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return ''


def _identifier(raw: bytes, chassis: bool) -> str:
    if not raw:
        return ''
    if raw[0] == (4 if chassis else 3) and len(raw) == 7:
        return _mac(raw[1:])
    if raw[0] == (5 if chassis else 4) and len(raw) > 2:
        return _address(raw[2:]) or _text(raw[2:])
    return _text(raw[1:])


def _neighbor(protocol: str, source: str) -> dict:
    return dict(protocol=protocol, source=source, chassis='', name='', port='',
                description='', system='', addresses=[], pvid=None, vlans=[], voice=[],
                capabilities=[], duplex='', ttl=0)


def _vlan(value: int) -> bool:
    return 1 <= value <= 4094


_LLDP_CAPABILITIES = {0: 'other', 1: 'repeater', 2: 'bridge', 3: 'wlan', 4: 'router',
                      5: 'telephone', 6: 'docsis', 7: 'station'}
_DOT1 = b'\x00\x80\xc2'
_MED = b'\x00\x12\xbb'


def _lldp_chassis(row: dict, value: bytes) -> None:
    row['chassis'] = _identifier(value, True)


def _lldp_port(row: dict, value: bytes) -> None:
    row['port'] = _identifier(value, False)


def _lldp_ttl(row: dict, value: bytes) -> None:
    if len(value) == 2:
        row['ttl'] = int.from_bytes(value, 'big')


def _lldp_text(key: str):
    def handler(row: dict, value: bytes) -> None:
        row[key] = _text(value)
    return handler


def _lldp_capabilities(row: dict, value: bytes) -> None:
    if len(value) == 4:
        enabled = int.from_bytes(value[2:4], 'big')
        row['capabilities'] = [name for bit, name in _LLDP_CAPABILITIES.items() if enabled & (1 << bit)]


def _lldp_management(row: dict, value: bytes) -> None:
    if len(value) < 2:
        return
    count, family = value[:2]
    if count >= 2 and count + 1 <= len(value) and family in (1, 2):
        address = _address(value[2:1 + count])
        if address and address not in row['addresses']:
            row['addresses'].append(address)


def _lldp_dot1(row: dict, subtype: int, data: bytes) -> None:
    if subtype == 1 and len(data) == 2:
        vid = int.from_bytes(data, 'big')
        if _vlan(vid):
            row['pvid'] = vid
    elif subtype == 3 and len(data) >= 3:
        vid, length = int.from_bytes(data[:2], 'big'), data[2]
        if _vlan(vid) and length <= len(data) - 3:
            row['vlans'].append({'id': vid, 'name': _text(data[3:3 + length])})


def _lldp_med(row: dict, subtype: int, data: bytes) -> None:
    if subtype == 2 and len(data) == 4:
        # LLDP-MED: aplicación, unknown/tagged, VID, prioridad y DSCP.
        policy = int.from_bytes(data[1:], 'big')
        vid = (policy >> 9) & 4095
        if data[0] in (1, 2) and not policy & 0x800000 and _vlan(vid):
            row['voice'].append({'id': vid, 'tagged': bool(policy & 0x400000)})


def _lldp_organization(row: dict, value: bytes) -> None:
    if len(value) < 4:
        return
    oui, subtype, data = value[:3], value[3], value[4:]
    if oui == _DOT1:
        _lldp_dot1(row, subtype, data)
    elif oui == _MED:
        _lldp_med(row, subtype, data)


_LLDP_HANDLERS = {
    1: _lldp_chassis, 2: _lldp_port, 3: _lldp_ttl,
    4: _lldp_text('description'), 5: _lldp_text('name'), 6: _lldp_text('system'),
    7: _lldp_capabilities, 8: _lldp_management, 127: _lldp_organization,
}


def _lldp(payload: bytes, source: str) -> dict | None:
    row = _neighbor('LLDP', source)
    seen = []
    offset = 0
    ended = False
    while offset + 2 <= len(payload):
        header = int.from_bytes(payload[offset:offset + 2], 'big')
        kind, size = header >> 9, header & 511
        offset += 2
        if offset + size > len(payload):
            return None
        value = payload[offset:offset + size]
        offset += size
        if kind == 0:
            ended = size == 0
            break
        seen.append(kind)
        handler = _LLDP_HANDLERS.get(kind)
        if handler:
            handler(row, value)
    if not ended or seen[:3] != [1, 2, 3] or not row['chassis'] or not row['port']:
        return None
    return row


def _cdp_addresses(value: bytes) -> list[str]:
    if len(value) < 4:
        return []
    found, offset = [], 4
    for _ in range(min(int.from_bytes(value[:4], 'big'), 128)):
        if offset + 2 > len(value):
            break
        protocol_type, size = value[offset:offset + 2]
        offset += 2
        if offset + size + 2 > len(value):
            break
        protocol = value[offset:offset + size]
        offset += size
        size = int.from_bytes(value[offset:offset + 2], 'big')
        offset += 2
        if offset + size > len(value):
            break
        raw = value[offset:offset + size]
        offset += size
        if ((protocol_type == 1 and protocol == b'\xcc' and size == 4)
                or (protocol_type == 2 and protocol.endswith(b'\x86\xdd') and size == 16)):
            address = _address(raw)
            if address and address not in found:
                found.append(address)
    return found


def _cdp_text(key: str):
    def handler(row: dict, value: bytes) -> None:
        row[key] = _text(value)
    return handler


def _cdp_addresses_into(row: dict, value: bytes) -> None:
    row['addresses'] = list(dict.fromkeys(row['addresses'] + _cdp_addresses(value)))


def _cdp_native_vlan(row: dict, value: bytes) -> None:
    if len(value) == 2:
        vid = int.from_bytes(value, 'big')
        if _vlan(vid):
            row['pvid'] = vid


def _cdp_duplex(row: dict, value: bytes) -> None:
    if len(value) == 1:
        row['duplex'] = 'full' if value[0] else 'half'


def _cdp_voice_vlan(row: dict, value: bytes) -> None:
    if len(value) == 3:
        vid = int.from_bytes(value[1:], 'big')
        if _vlan(vid):
            row['voice'].append({'id': vid, 'tagged': True})


_CDP_HANDLERS = {
    1: _cdp_text('chassis'), 3: _cdp_text('port'), 5: _cdp_text('description'),
    6: _cdp_text('system'), 20: _cdp_text('name'),
    2: _cdp_addresses_into, 22: _cdp_addresses_into,
    10: _cdp_native_vlan, 11: _cdp_duplex, 14: _cdp_voice_vlan,
}


def _cdp(payload: bytes, source: str) -> dict | None:
    if len(payload) < 4 or payload[0] not in (1, 2):
        return None
    row = _neighbor('CDP', source)
    row['ttl'] = payload[1]
    offset = 4
    while offset + 4 <= len(payload):
        kind, size = struct.unpack('!HH', payload[offset:offset + 4])
        if size < 4 or offset + size > len(payload):
            return None
        value = payload[offset + 4:offset + size]
        offset += size
        handler = _CDP_HANDLERS.get(kind)
        if handler:
            handler(row, value)
    if not row['chassis'] or not row['port']:
        return None
    row['name'] = row['name'] or row['chassis']
    return row


def parse_frame(frame: bytes) -> tuple[dict | None, list[int]]:
    """Devuelve anuncio y VLAN observadas. Un paquete inválido nunca rompe la sesión."""
    if len(frame) < 14:
        return None, []
    source = _mac(frame[6:12])
    kind = int.from_bytes(frame[12:14], 'big')
    offset, vlans = 14, []
    while kind in (0x8100, 0x88a8, 0x9100):
        if offset + 4 > len(frame):
            return None, vlans
        tag, kind = struct.unpack('!HH', frame[offset:offset + 4])
        if _vlan(tag & 4095):
            vlans.append(tag & 4095)
        offset += 4
    payload = frame[offset:]
    if kind == 0x88cc:
        return _lldp(payload, source), vlans
    if kind <= 1500 and len(payload) >= kind:
        payload = payload[:kind]
        if payload.startswith(b'\xaa\xaa\x03\x00\x00\x0c\x20\x00'):
            return _cdp(payload[8:], source), vlans
    return None, vlans
