"""Servidores de prueba: catalogo, ajustes de cada uno y lectura de su registro.

Los textos son claves de `i18n`. La interfaz grafica las traduce, asi el idioma
se cambia sin reconstruir nada.
"""
from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

RANDOM = '@random'
YES = '1'
NO = '0'

IFACE_REQUIRED = 'interface'
IFACE_OPTIONAL = 'interface_any'


@dataclass(frozen=True)
class ServerField:
    key: str
    label: str
    kind: str               # interface | interface_any | text | choice | toggle
    default: str = ''
    options: tuple[tuple[str, str], ...] = ()    # (valor, clave de texto)
    when: tuple[str, tuple[str, ...]] | None = None   # solo se muestra si ajuste `key` vale alguno
    placeholder: str = ''


@dataclass(frozen=True)
class ServerColumn:
    key: str
    title: str
    share: int


@dataclass(frozen=True)
class ServerKind:
    id: str
    icon: str
    title: str
    subtitle: str
    hint: str
    fields: tuple[ServerField, ...]
    columns: tuple[ServerColumn, ...]
    unique: str = ''        # columna que identifica una fila: una nueva con el mismo valor la reemplaza

    def field(self, key: str) -> ServerField:
        return next(item for item in self.fields if item.key == key)

    def defaults(self) -> dict[str, str]:
        return {item.key: item.default for item in self.fields}

    def to_dict(self) -> dict:
        return {
            'id': self.id, 'icon': self.icon, 'title': self.title,
            'subtitle': self.subtitle, 'hint': self.hint,
            'fields': [{
                'key': item.key, 'label': item.label, 'kind': item.kind, 'default': item.default,
                'placeholder': item.placeholder,
                'options': [{'value': value, 'label': label} for value, label in item.options],
                'when': None if item.when is None else {'key': item.when[0], 'in': list(item.when[1])},
            } for item in self.fields],
            'columns': [{'key': item.key, 'title': item.title, 'share': item.share}
                        for item in self.columns],
        }


_EVENTS = (ServerColumn('time', 'srvTime', 15), ServerColumn('client', 'srvClient', 24),
           ServerColumn('event', 'srvEvent', 61))
_LEASES = (ServerColumn('time', 'srvTime', 15), ServerColumn('ip', 'srvIp', 25),
           ServerColumn('mac', 'srvMac', 30), ServerColumn('name', 'srvHost', 30))

_ANY_INTERFACE = ServerField('iface', 'iface', IFACE_OPTIONAL)
_YES_NO = (('1', 'serverYes'), ('0', 'serverNo'))


def _port(default: str, key: str = 'port', label: str = 'fieldPort',
          when: tuple[str, tuple[str, ...]] | None = None) -> ServerField:
    return ServerField(key, label, 'text', default, when=when)


KINDS: tuple[ServerKind, ...] = (
    ServerKind('iperf', 'gauge', 'srvIperf', 'srvIperfSub', 'srvIperfHint', (
        _ANY_INTERFACE,
        _port('5201'),
        ServerField('once', 'serverOnce', 'toggle', NO, _YES_NO),
    ), _EVENTS),
    ServerKind('tftp', 'file', 'srvTftp', 'srvTftpSub', 'srvTftpHint', (
        _ANY_INTERFACE,
        _port('69'),
        ServerField('writable', 'serverWritable', 'toggle', YES, _YES_NO),
    ), _EVENTS),
    ServerKind('sftp', 'lock', 'srvSftp', 'srvSftpSub', 'srvSftpHint', (
        _ANY_INTERFACE,
        _port('2222'),
        ServerField('user', 'serverUser', 'text', 'mulita'),
        ServerField('password', 'serverPassword', 'text', RANDOM),
        ServerField('writable', 'serverWritable', 'toggle', YES, _YES_NO),
    ), _EVENTS),
    ServerKind('web', 'globe', 'srvWeb', 'srvWebSub', 'srvWebHint', (
        _ANY_INTERFACE,
        ServerField('mode', 'serverMode', 'choice', 'http',
                    (('http', 'HTTP'), ('https', 'HTTPS'), ('both', 'serverBoth'))),
        _port('80', 'http_port', 'serverHttpPort', ('mode', ('http', 'both'))),
        _port('443', 'https_port', 'serverHttpsPort', ('mode', ('https', 'both'))),
        ServerField('share', 'serverShare', 'toggle', YES, _YES_NO),
    ), _EVENTS),
    ServerKind('dns', 'search', 'srvDns', 'srvDnsSub', 'srvDnsHint', (
        ServerField('iface', 'iface', IFACE_REQUIRED),
        _port('53'),
        ServerField('name', 'serverTestName', 'text', 'mulita.test'),
        ServerField('answer', 'serverAnswer', 'text', '', placeholder='serverAuto'),
        ServerField('upstream', 'serverUpstream', 'text', '', placeholder='serverNone'),
    ), _EVENTS),
    ServerKind('dhcp', 'ethernet', 'srvDhcp', 'srvDhcpSub', 'srvDhcpHint', (
        ServerField('iface', 'iface', IFACE_REQUIRED),
        ServerField('first', 'serverFrom', 'text', '', placeholder='serverAuto'),
        ServerField('last', 'serverTo', 'text', '', placeholder='serverAuto'),
        ServerField('gateway', 'fieldGateway', 'text', '', placeholder='serverThisPort'),
        ServerField('dns', 'srvDns', 'text', '', placeholder='serverThisPort'),
        ServerField('hours', 'serverLease', 'text', '1'),
    ), _LEASES, unique='mac'),
    ServerKind('ntp', 'clock', 'srvNtp', 'srvNtpSub', 'srvNtpHint', (
        _ANY_INTERFACE,
        _port('123'),
        ServerField('stratum', 'serverStratum', 'text', '3'),
    ), _EVENTS),
)

_BY_ID = {kind.id: kind for kind in KINDS}


def kind_by_id(identifier: str) -> ServerKind:
    try:
        return _BY_ID[identifier]
    except KeyError:
        raise KeyError(f'Servidor desconocido: {identifier}') from None


# --- Lectura del registro ---------------------------------------------------------------

_DNSMASQ_PREFIX = re.compile(r'^dnsmasq[\w-]*(?:\[\d+\])?:\s*')
_DNS_QUERY = re.compile(r'^query\[(\w+)\]\s+(\S+)\s+from\s+(\S+)')
_DHCP_ACK = re.compile(r'DHCPACK\([^)]*\)\s+(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9A-Fa-f:]{17})(?:\s+(\S.*))?$')
_SSH_LOGIN = re.compile(r'(?:Accepted|Failed) \S+ for (?:invalid user )?\S+ from (\S+) port \d+')
_SSH_CLOSE = re.compile(r'(?:Connection closed by|Disconnected from|Connection reset by)'
                        r'(?: (?:authenticating|invalid) user \S+)? (\S+) port \d+')
_IPERF_PEER = re.compile(r'Accepted connection from ([0-9A-Fa-f:.]+),')
_NOISE = re.compile(r'^[-=\s]*$')


def _tabbed(line: str) -> dict | None:
    """Formato de los servidores propios: `cliente<TAB>evento`."""
    client, separator, event = line.partition('\t')
    if not separator:
        return {'client': '', 'event': line}
    return {'client': client.strip(), 'event': event.strip()}


def _iperf(line: str) -> dict | None:
    if _NOISE.match(line):
        return None
    found = _IPERF_PEER.search(line)
    return {'client': found.group(1) if found else '', 'event': line}


def _dns(line: str) -> dict | None:
    text = _DNSMASQ_PREFIX.sub('', line)
    found = _DNS_QUERY.match(text)
    if found:
        return {'client': found.group(3), 'event': f'{found.group(1)} {found.group(2)}'}
    return {'client': '', 'event': text}


def _dhcp(line: str) -> dict | None:
    found = _DHCP_ACK.search(line)
    if not found:
        return None
    return {'ip': found.group(1), 'mac': found.group(2).lower(), 'name': (found.group(3) or '').strip()}


def _ssh(line: str) -> dict | None:
    found = _SSH_LOGIN.search(line) or _SSH_CLOSE.search(line)
    return {'client': found.group(1) if found else '', 'event': line}


_READERS: dict[str, Callable[[str], dict | None]] = {
    'iperf': _iperf, 'tftp': _tabbed, 'sftp': _ssh, 'web': _tabbed,
    'dns': _dns, 'dhcp': _dhcp, 'ntp': _tabbed,
}


def _clock() -> str:
    return time.strftime('%H:%M:%S')


class ServerLog:
    """Filas del registro de un servidor y las ultimas lineas crudas, para explicar un fallo."""

    LIMIT = 500
    TAIL = 8

    def __init__(self, kind: ServerKind, clock: Callable[[], str] = _clock):
        self._kind = kind
        self._read = _READERS[kind.id]
        self._clock = clock
        self._pending = ''
        self.rows: list[dict] = []
        self.tail: deque[str] = deque(maxlen=self.TAIL)

    def clear(self) -> None:
        self._pending = ''
        self.rows = []
        self.tail.clear()

    def feed(self, text: str) -> bool:
        """Devuelve True si cambiaron las filas."""
        self._pending += text.replace('\r', '')
        changed = False
        while '\n' in self._pending:
            line, self._pending = self._pending.split('\n', 1)
            changed |= self._take(line)
        return changed

    def flush(self) -> bool:
        line, self._pending = self._pending, ''
        return self._take(line)

    def _take(self, line: str) -> bool:
        line = line.strip()
        if not line:
            return False
        self.tail.append(line[:500])
        row = self._read(line)
        if row is None:
            return False
        row['time'] = self._clock()
        key = self._kind.unique
        if key:
            for index, existing in enumerate(self.rows):
                if existing.get(key) == row.get(key):
                    self.rows[index] = row
                    return True
        self.rows.append(row)
        if len(self.rows) > self.LIMIT:
            del self.rows[:len(self.rows) - self.LIMIT]
        return True

    def newest_first(self) -> list[dict]:
        return list(reversed(self.rows))
