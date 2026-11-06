"""Avance en vivo y lectura del XML de resultados de Nmap."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from xml.etree import ElementTree

_VULNERABLE = re.compile(r'(?<!NOT )VULNERABLE', re.IGNORECASE)

_PHASE = re.compile(r'^(.*?)\s+Timing:\s+About\s+([\d.]+)%\s+done(?:;.*?\(([0-9:]+) remaining\))?')

_UNDERGOING = re.compile(r'undergoing\s+(.+)$')

_ELAPSED = re.compile(r'Stats:\s*(\d+:\d\d:\d\d)\s+elapsed')

# --- Avance informado por Nmap -----------------------------------------------------------


@dataclass
class Progress:
    elapsed: str = ''
    phase: str = ''
    percent: str = ''
    remaining: str = ''
    phase_only: bool = False

    def view(self) -> dict:
        return {'elapsed': self.elapsed, 'phase': self.phase, 'percent': self.percent,
                'remaining': self.remaining, 'phaseOnly': self.phase_only}


def update_progress(progress: Progress, text: str) -> bool:
    """Solo copia lo que Nmap escribió. Si no hay porcentaje, queda vacío."""
    changed = False
    for line in (text or '').splitlines():
        line = line.strip()
        elapsed = _ELAPSED.search(line)
        if elapsed:
            progress.elapsed = elapsed.group(1)
            changed = True
            undergoing = _UNDERGOING.search(line)
            if undergoing:
                progress.phase = undergoing.group(1).strip()
        phase = _PHASE.search(line)
        if phase:
            progress.phase = phase.group(1).strip() or progress.phase
            progress.percent = phase.group(2)
            progress.remaining = phase.group(3) or ''
            progress.phase_only = True
            changed = True
    return changed


# --- XML ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanDocument:
    hosts: tuple[dict, ...]
    partial: bool
    complete: bool


def parse_xml(text: str, today: date | None = None) -> ScanDocument:
    """Lee el XML. Si está cortado, conserva los equipos que quedaron completos."""
    raw = (text or '').strip()
    if not raw:
        return ScanDocument((), True, False)
    try:
        root = ElementTree.fromstring(raw)
        repaired = False
    except ElementTree.ParseError:
        cut = raw.rfind('</host>')
        if cut < 0 or '<nmaprun' not in raw[:cut]:
            return ScanDocument((), True, False)
        try:
            root = ElementTree.fromstring(raw[:cut + len('</host>')] + '</nmaprun>')
        except ElementTree.ParseError:
            return ScanDocument((), True, False)
        repaired = True
    hosts = tuple(_host(node, today or date.today()) for node in root.findall('host'))
    finished = root.find('runstats/finished')
    complete = finished is not None and finished.get('exit') == 'success' and not repaired
    return ScanDocument(hosts, not complete, complete)


def _host(node, today: date) -> dict:
    status = node.find('status')
    ip = mac = vendor = ''
    for address in node.findall('address'):
        kind = address.get('addrtype')
        if kind == 'mac':
            mac = address.get('addr', '')
            vendor = address.get('vendor', '')
        elif kind in ('ipv4', 'ipv6') and not ip:
            ip = address.get('addr', '')
    names = [item.get('name', '') for item in node.findall('hostnames/hostname') if item.get('name')]
    matches = [{'name': item.get('name', ''), 'accuracy': item.get('accuracy', '')}
               for item in node.findall('os/osmatch') if item.get('name')]
    shown = ', '.join(f"{item['name']} ({item['accuracy']}%)" for item in matches[:2])
    return {
        'ip': ip,
        'names': names,
        'state': status.get('state', '') if status is not None else '',
        'reason': status.get('reason', '') if status is not None else '',
        'mac': mac,
        'vendor': vendor,
        'os': shown,
        'osMatches': matches,
        'ports': [_port(item, today) for item in node.findall('ports/port')],
        'scripts': [_script(item, today) for item in node.findall('hostscript/script')],
    }


def _port(node, today: date) -> dict:
    state = node.find('state')
    service = node.find('service')
    return {
        'port': node.get('portid', ''),
        'protocol': node.get('protocol', ''),
        'state': state.get('state', '') if state is not None else '',
        'reason': state.get('reason', '') if state is not None else '',
        'service': service.get('name', '') if service is not None else '',
        'product': service.get('product', '') if service is not None else '',
        'version': service.get('version', '') if service is not None else '',
        'scripts': [_script(item, today) for item in node.findall('script')],
    }


def _script(node, today: date) -> dict:
    output = node.get('output', '') or ''
    kind = script_kind(output)
    return {
        'id': node.get('id', ''),
        'kind': kind,
        'output': output.strip(),
        'note': smb_note(node.get('id', ''), output),
        'lines': cert_lines(output, today) if node.get('id') == 'ssl-cert' else [],
        'days': cert_days(output, today) if node.get('id') == 'ssl-cert' else None,
    }


def script_kind(output: str) -> str:
    """Separa vulnerabilidad informada, comprobación correcta, error e inconcluso.

    `NOT VULNERABLE` no cuenta como vulnerabilidad. Una versión de servicio no pasa por acá.
    """
    if _VULNERABLE.search(output or ''):
        return 'vulnerable'
    text = (output or '').strip().upper()
    if text.startswith('ERROR') or '\nERROR' in text:
        return 'error'
    lowered = (output or '').lower()
    if any(mark in lowered for mark in ('inconclusive', 'could not', 'unknown result', 'no reply')):
        return 'inconclusive'
    if 'NOT VULNERABLE' in text:
        return 'ok'
    return 'info'


def smb_note(script_id: str, output: str) -> str:
    text = (output or '').lower()
    if script_id == 'smb-protocols' and 'smbv1' in text.replace(' ', ''):
        return 'nmapSmbV1'
    if 'signing' not in text and 'message signing' not in text:
        return ''
    if 'not required' in text or 'disabled' in text:
        return 'nmapSmbSignOff' if 'disabled' in text else 'nmapSmbSignOptional'
    if 'required' in text:
        return 'nmapSmbSignRequired'
    return ''


def cert_lines(output: str, today: date) -> list[dict]:
    found = _cert_fields(output)
    mapping = (
        ('Subject', 'nmapCertSubject'),
        ('Issuer', 'nmapCertIssuer'),
        ('Subject Alternative Name', 'nmapCertSan'),
        ('Not valid before', 'nmapCertFrom'),
        ('Not valid after', 'nmapCertUntil'),
        ('SHA-256', 'nmapCertSha256'),
        ('SHA-1', 'nmapCertSha1'),
    )
    lines = [{'label': key, 'value': found[name]} for name, key in mapping if found.get(name)]
    days = cert_days(output, today)
    if days is not None:
        lines.append({'label': 'nmapCertDays', 'value': str(days)})
    return lines


def cert_days(output: str, today: date) -> int | None:
    raw = _cert_fields(output).get('Not valid after', '')
    expiry = _cert_date(raw)
    if expiry is None:
        return None
    return (expiry.date() - today).days


def _cert_fields(output: str) -> dict[str, str]:
    found = {}
    for line in (output or '').splitlines():
        if ':' not in line:
            continue
        name, _, value = line.partition(':')
        found.setdefault(name.strip(), value.strip())
    return found


def _cert_date(value: str) -> datetime | None:
    text = re.sub(r'\.\d+', '', (value or '').strip()).replace('Z', '+0000')
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def open_tcp_ports(hosts: tuple[dict, ...] | list[dict]) -> str:
    found = sorted({int(port['port']) for host in hosts for port in host.get('ports', [])
                    if port.get('protocol') == 'tcp' and port.get('state') == 'open' and str(port.get('port', '')).isdigit()})
    return ','.join(str(port) for port in found)
