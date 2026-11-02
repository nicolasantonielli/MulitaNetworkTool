"""Analisis TLS con testssl.sh: destino, modos y lectura del informe JSON."""
from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass

from mulita.core import validation
from mulita.core.errors import ValidationError
from mulita.core.messages import message

DEFAULT_PORT = 443
DEFAULT_MODE = 'certificate'

# Que revisa cada modo. El completo junta los otros tres: en la Pi tarda minutos.
MODES: dict[str, tuple[str, list[str]]] = {
    'certificate': ('tlsModeCertificate', ['-S']),
    'protocols': ('tlsModeProtocols', ['-p', '-s']),
    'vulnerabilities': ('tlsModeVulns', ['-U']),
    'full': ('tlsModeFull', ['-S', '-p', '-s', '-U']),
}

SECTIONS = ('certificate', 'protocols', 'ciphers', 'vulnerabilities', 'other')


_VULNERABILITIES = {
    'heartbleed', 'CCS', 'ticketbleed', 'ROBOT', 'secure_renego', 'secure_client_renego',
    'CRIME_TLS', 'BREACH', 'POODLE_SSL', 'fallback_SCSV', 'SWEET32', 'FREAK', 'DROWN',
    'DROWN_hint', 'LOGJAM', 'LOGJAM-common_primes', 'BEAST', 'BEAST_CBC_TLS1', 'LUCKY13',
    'winshock', 'RC4',
}

# testssl.sh agrega " <cert#2>" cuando el servidor presenta mas de un certificado.
_COPY = re.compile(r'^(\S+)\s*<cert#(\d+)>$')
_IGNORED = {'cert', 'scanTime'}


@dataclass(frozen=True)
class TlsTarget:
    host: str
    port: int = DEFAULT_PORT

    @property
    def argument(self) -> str:
        host = f'[{self.host}]' if ':' in self.host else self.host
        return f'{host}:{self.port}'

    @property
    def label(self) -> str:
        return self.argument


@dataclass(frozen=True)
class TlsFinding:
    id: str
    severity: str
    text: str
    section: str
    cve: str = ''
    copy: int = 0


def parse_target(value: str) -> TlsTarget:
    """Acepta host, host:puerto, [IPv6]:puerto o una URL https://host:puerto/ruta."""
    text = (value or '').strip()
    text = re.sub(r'^[A-Za-z][A-Za-z0-9+.-]*://', '', text)
    text = re.split(r'[/?#]', text, maxsplit=1)[0]
    if '@' in text:
        text = text.rsplit('@', 1)[1]
    port = DEFAULT_PORT
    if text.startswith('['):
        end = text.find(']')
        if end < 0:
            raise ValidationError(message('badHost', value=text))
        host, tail = text[1:end], text[end + 1:]
        if tail:
            if not tail.startswith(':'):
                raise ValidationError(message('badHost', value=text))
            port = validation.port_number(tail[1:], message('fieldPort'))
    elif text.count(':') == 1:
        host, _, tail = text.partition(':')
        port = validation.port_number(tail, message('fieldPort'))
    else:
        host = text
    return TlsTarget(_address(host), port)


def _address(host: str) -> str:
    """Nombre o IP. Las IPv6 pueden empezar con ':' y `validation.host` no las admite."""
    if ':' in host:
        try:
            ipaddress.ip_address(host.split('%', 1)[0])
        except ValueError:
            raise ValidationError(message('badHost', value=host)) from None
        return host
    return validation.host(host)


def mode_flags(mode: str) -> list[str]:
    try:
        return list(MODES[mode][1])
    except KeyError:
        raise ValidationError(message('badTlsMode', value=mode or message('empty'))) from None


def parse_report(raw: str) -> tuple[TlsFinding, ...]:
    """Lee el JSON de `--jsonfile`. Tolera un archivo cortado porque se detuvo el analisis."""
    findings: list[TlsFinding] = []
    for entry in _entries(_load(raw)):
        found = _finding(entry)
        if found is not None:
            findings.append(found)
    return tuple(findings)


def _load(raw: str):
    text = (raw or '').strip()
    if not text:
        return []
    try:
        return json.loads(text)
    except ValueError:
        pass
    decoder = json.JSONDecoder()
    found = []
    index = 0
    while True:
        start = text.find('{', index)
        if start < 0:
            return found
        try:
            value, end = decoder.raw_decode(text, start)
        except ValueError:
            index = start + 1
            continue
        found.append(value)
        index = end


def _entries(node):
    """Recorre listas y objetos anidados (`scanResult`, `serverDefaults`...) hasta los hallazgos."""
    if isinstance(node, list):
        for item in node:
            yield from _entries(item)
    elif isinstance(node, dict):
        if 'id' in node and 'finding' in node:
            yield node
        else:
            for value in node.values():
                yield from _entries(value)


def _finding(entry: dict) -> TlsFinding | None:
    raw_id = str(entry.get('id', '')).strip()
    text = ' '.join(str(entry.get('finding', '')).split())
    if not raw_id or 'BEGIN CERTIFICATE' in text:
        return None
    copy = _COPY.match(raw_id)
    if copy:
        base, number = copy.group(1), int(copy.group(2))
    else:
        parts = raw_id.split()
        base, number = parts[0], 0
    if base in _IGNORED:
        return None
    severity = str(entry.get('severity', 'INFO')).strip().upper() or 'INFO'
    return TlsFinding(base, severity, text, section_of(base),
                      str(entry.get('cve', '')).strip(), number)


def section_of(identifier: str) -> str:
    if identifier in ('SSLv2', 'SSLv3', 'TLS1', 'TLS1_1', 'TLS1_2', 'TLS1_3') or identifier.startswith(('ALPN', 'NPN')):
        return 'protocols'
    if identifier in _VULNERABILITIES:
        return 'vulnerabilities'
    if identifier.startswith(('cert', 'intermediate_cert', 'chain', 'OCSP', 'DNS_CAA')):
        return 'certificate'
    if identifier.startswith(('cipher', 'FS', 'PFS')):
        return 'ciphers'
    return 'other'
