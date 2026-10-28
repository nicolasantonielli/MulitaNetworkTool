"""Analisis TLS con testssl.sh: destino, modos, lectura del informe JSON y etiquetas."""
from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass

from mulita.core import validation
from mulita.core.errors import ValidationError
from mulita.presentation.i18n import tr

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
_SECTION_KEYS = {
    'certificate': 'tlsSecCertificate',
    'protocols': 'tlsSecProtocols',
    'ciphers': 'tlsSecCiphers',
    'vulnerabilities': 'tlsSecVulns',
    'other': 'tlsSecOther',
}

_SEVERITY_KEYS = {
    'CRITICAL': 'tlsSevCritical',
    'HIGH': 'tlsSevHigh',
    'MEDIUM': 'tlsSevMedium',
    'LOW': 'tlsSevLow',
    'WARN': 'tlsSevWarn',
    'OK': 'tlsSevOk',
    'INFO': 'tlsSevInfo',
}
_TONES = {
    'CRITICAL': 'danger', 'HIGH': 'danger',
    'MEDIUM': 'warning', 'LOW': 'warning', 'WARN': 'warning',
    'OK': 'success',
}
# Se cuentan en el resumen, de lo mas grave a lo mas sano. INFO no aporta.
_COUNTED = ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'WARN', 'OK')

_PROTOCOLS = {
    'SSLv2': 'SSL 2.0', 'SSLv3': 'SSL 3.0', 'TLS1': 'TLS 1.0',
    'TLS1_1': 'TLS 1.1', 'TLS1_2': 'TLS 1.2', 'TLS1_3': 'TLS 1.3',
}
_VULNERABILITIES = {
    'heartbleed', 'CCS', 'ticketbleed', 'ROBOT', 'secure_renego', 'secure_client_renego',
    'CRIME_TLS', 'BREACH', 'POODLE_SSL', 'fallback_SCSV', 'SWEET32', 'FREAK', 'DROWN',
    'DROWN_hint', 'LOGJAM', 'LOGJAM-common_primes', 'BEAST', 'BEAST_CBC_TLS1', 'LUCKY13',
    'winshock', 'RC4',
}
# Los textos del certificado se traducen. El resto conserva el nombre de testssl.sh,
# que es el que figura en la documentacion (SWEET32, ROBOT, heartbleed...).
_CERT_LABELS = {
    'cert_commonName': 'tlsIdCommonName',
    'cert_subjectAltName': 'tlsIdAltNames',
    'cert_caIssuers': 'tlsIdIssuer',
    'cert_notBefore': 'tlsIdNotBefore',
    'cert_notAfter': 'tlsIdNotAfter',
    'cert_expirationStatus': 'tlsIdExpiry',
    'cert_validityPeriod': 'tlsIdValidity',
    'cert_signatureAlgorithm': 'tlsIdSignature',
    'cert_keySize': 'tlsIdKeySize',
    'cert_trust': 'tlsIdTrust',
    'cert_chain_of_trust': 'tlsIdChain',
    'chain_of_trust': 'tlsIdChain',
    'cert_serialNumber': 'tlsIdSerial',
    'cert_fingerprintSHA256': 'tlsIdSha256',
    'cert_fingerprintSHA1': 'tlsIdSha1',
    'OCSP_stapling': 'tlsIdOcsp',
    'DNS_CAA': 'tlsIdCaa',
    'certificate_transparency': 'tlsIdTransparency',
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
            raise ValidationError(tr('badHost', value=text))
        host, tail = text[1:end], text[end + 1:]
        if tail:
            if not tail.startswith(':'):
                raise ValidationError(tr('badHost', value=text))
            port = validation.port_number(tail[1:], tr('fieldPort'))
    elif text.count(':') == 1:
        host, _, tail = text.partition(':')
        port = validation.port_number(tail, tr('fieldPort'))
    else:
        host = text
    return TlsTarget(_address(host), port)


def _address(host: str) -> str:
    """Nombre o IP. Las IPv6 pueden empezar con ':' y `validation.host` no las admite."""
    if ':' in host:
        try:
            ipaddress.ip_address(host.split('%', 1)[0])
        except ValueError:
            raise ValidationError(tr('badHost', value=host)) from None
        return host
    return validation.host(host)


def mode_flags(mode: str) -> list[str]:
    try:
        return list(MODES[mode][1])
    except KeyError:
        raise ValidationError(tr('badTlsMode', value=mode or tr('empty'))) from None


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
    if identifier in _PROTOCOLS or identifier.startswith(('ALPN', 'NPN')):
        return 'protocols'
    if identifier in _VULNERABILITIES:
        return 'vulnerabilities'
    if identifier.startswith(('cert', 'intermediate_cert', 'chain', 'OCSP', 'DNS_CAA')):
        return 'certificate'
    if identifier.startswith(('cipher', 'FS', 'PFS')):
        return 'ciphers'
    return 'other'


def tone_of(severity: str) -> str:
    return _TONES.get(severity, 'muted')


def severity_label(severity: str) -> str:
    key = _SEVERITY_KEYS.get(severity)
    return tr(key) if key else severity


def section_label(section: str) -> str:
    return tr(_SECTION_KEYS.get(section, 'tlsSecOther'))


def test_label(finding: TlsFinding) -> str:
    key = _CERT_LABELS.get(finding.id)
    label = tr(key) if key else _PROTOCOLS.get(finding.id, finding.id)
    return f'{label} #{finding.copy}' if finding.copy else label


def summarize(findings: tuple[TlsFinding, ...]) -> list[dict]:
    counts = {severity: 0 for severity in _COUNTED}
    for item in findings:
        if item.severity in counts:
            counts[item.severity] += 1
    return [{'severity': severity, 'label': severity_label(severity),
             'tone': tone_of(severity), 'count': counts[severity]}
            for severity in _COUNTED if counts[severity]]


def grouped(findings: tuple[TlsFinding, ...]) -> list[dict]:
    """Filas para la tabla: un encabezado por seccion y sus hallazgos debajo."""
    rows: list[dict] = []
    for section in SECTIONS:
        items = [item for item in findings if item.section == section]
        if not items:
            continue
        rows.append({'header': True, 'title': section_label(section)})
        for item in items:
            rows.append({
                'header': False,
                'severity': severity_label(item.severity),
                'tone': tone_of(item.severity),
                'test': test_label(item),
                'result': item.text + (f'  ({item.cve})' if item.cve else ''),
            })
    return rows
