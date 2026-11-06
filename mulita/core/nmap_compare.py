"""Comparacion de dos escaneos Nmap guardados."""
from __future__ import annotations


def compare_scans(before: list[dict], after: list[dict]) -> dict:
    """Diferencias entre dos informes. Un puerto `open|filtered` no se toma como abierto."""
    def up(hosts):
        return {host['ip']: host for host in hosts if host.get('ip') and host.get('state') == 'up'}

    def opened(hosts):
        found = {}
        for host in hosts:
            for port in host.get('ports', []):
                if port.get('state') == 'open':
                    found[(host['ip'], port.get('protocol', ''), port.get('port', ''))] = port
        return found

    previous, current = up(before), up(after)
    previous_ports, current_ports = opened(before), opened(after)
    changes = []
    for key in sorted(set(previous_ports) & set(current_ports)):
        old, new = _service_text(previous_ports[key]), _service_text(current_ports[key])
        if old != new:
            host, protocol, port = key
            changes.append(f'{host} {protocol}/{port}: {old or "—"} -> {new or "—"}')
    return {
        'newHosts': sorted(set(current) - set(previous)),
        'goneHosts': sorted(set(previous) - set(current)),
        'newPorts': [_port_text(key) for key in sorted(set(current_ports) - set(previous_ports))],
        'gonePorts': [_port_text(key) for key in sorted(set(previous_ports) - set(current_ports))],
        'changes': changes,
    }


def _service_text(port: dict) -> str:
    return ' '.join(part for part in (port.get('service', ''), port.get('product', ''), port.get('version', '')) if part)


def _port_text(key: tuple[str, str, str]) -> str:
    host, protocol, port = key
    return f'{host} {protocol}/{port}'
