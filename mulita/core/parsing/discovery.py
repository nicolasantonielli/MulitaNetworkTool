"""Parsers for discovery data."""
from __future__ import annotations

import re
from mulita.core.models import HostSighting, PortFinding


_SCAN_HOST = re.compile(r'^Nmap scan report for (?P<host>.+)$')


_SCAN_PORT = re.compile(
    r'^(?P<port>\d+)/(?P<protocol>tcp|udp|sctp|ip)\s+(?P<state>\S+)'
    r'(?:\s+(?P<service>.*\S))?\s*$',
    re.IGNORECASE)


_DISCOVERY_IP = re.compile(r'\b(\d{1,3}(?:\.\d{1,3}){3})\b')


_DISCOVERY_MAC = re.compile(r'\b((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\b')


def parse_discovery_line(line: str) -> HostSighting | None:
    """Una linea parseable de netdiscover: IP, MAC, cantidad y fabricante."""
    text = (line or '').strip()
    ip = _DISCOVERY_IP.search(text)
    mac = _DISCOVERY_MAC.search(text)
    if not ip or not mac or mac.start() < ip.end():
        return None
    count = ''
    vendor = ''
    rest = text[mac.end():].strip().split(None, 2)
    if rest and rest[0].isdigit():
        count = rest[0]
        if len(rest) == 3:
            vendor = rest[2].strip()
        elif len(rest) == 2 and not rest[1].isdigit():
            vendor = rest[1].strip()
    elif rest:
        vendor = ' '.join(rest).strip()
    return HostSighting(ip.group(1), mac.group(1).upper(), count, vendor)


def parse_port_scan(text: str) -> tuple[PortFinding, ...]:
    """Informe normal de nmap: un puerto por linea, bajo cada host."""
    host = ''
    found: list[PortFinding] = []
    for line in (text or '').splitlines():
        report = _SCAN_HOST.match(line.strip())
        if report:
            host = report.group('host').strip()
            continue
        port = _SCAN_PORT.match(line.strip())
        if not port or not host:
            continue
        found.append(PortFinding(
            host=host,
            port=port.group('port'),
            protocol=port.group('protocol').lower(),
            state=port.group('state').lower(),
            service=(port.group('service') or '').strip(),
        ))
    return tuple(found)
