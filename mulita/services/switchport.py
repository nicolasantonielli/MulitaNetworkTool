"""Identificación de la boca conectada, sin modificar IP ni configuración del switch."""
from __future__ import annotations

import json
import socket
import struct
import threading
import time
from datetime import datetime
from pathlib import Path

from mulita.core import validation
from mulita.core.errors import CommandFailedError
from mulita.core.switchport import parse_frame
from mulita.presentation.i18n import tr


def read_link(interface: str, root: Path = Path('/sys/class/net')) -> dict:
    folder = root / interface

    def read(name):
        try:
            return (folder / name).read_text().strip()
        except OSError:
            return ''

    speed = read('speed')
    return {'carrier': read('carrier'), 'speed': speed if speed.isdigit() else '',
            'duplex': read('duplex'), 'mac': read('address'),
            'rxErrors': read('statistics/rx_errors'), 'txErrors': read('statistics/tx_errors')}


class SwitchPortService:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.cancelled = threading.Event()

    def stop(self) -> None:
        self.cancelled.set()

    def scan(self, interface: str, seconds: int, cancelled: threading.Event,
             update, simulated: bool = False) -> dict:
        interface = validation.interface_name(interface)
        seconds = validation.integer_between(str(seconds), 5, 180, tr('switchDuration'))
        started = time.monotonic()
        report = {'interface': interface, 'started': datetime.now().isoformat(timespec='seconds'),
                  'elapsed': 0, 'simulated': simulated, 'neighbors': [], 'vlans': [],
                  'frames': 0, 'link': {}, 'cancelled': False}
        if simulated:
            report['link'] = {'carrier': '1', 'speed': '1000', 'duplex': 'full',
                              'mac': '02:00:00:00:00:01', 'rxErrors': '0', 'txErrors': '0'}
            report['neighbors'] = [{'protocol': 'LLDP', 'source': '02:00:00:00:00:02',
                'chassis': '02:00:00:00:00:02', 'name': 'Switch DEMO', 'port': 'Gi1/0/24',
                'description': 'Puerto de demostración', 'system': 'DEMO',
                'addresses': ['192.0.2.1'], 'pvid': 20, 'vlans': [], 'voice': [],
                'capabilities': ['bridge'], 'ttl': 120, 'lastSeen': report['started']}]
            report['cancelled'] = cancelled.is_set()
            update(json.loads(json.dumps(report)))
            return report
        if not hasattr(socket, 'AF_PACKET'):
            raise CommandFailedError(tr('switchLinux'))
        neighbors: dict[tuple, tuple[float, dict]] = {}
        observed: set[int] = set()
        last_update = -1.0
        try:
            with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3)) as receiver:
                receiver.bind((interface, 0))
                receiver.settimeout(0.25)
                # PACKET_AUXDATA conserva la VLAN quitada por el offload de la NIC.
                receiver.setsockopt(263, 8, 1)
                # Membresía promisc solo de este socket; el kernel la libera al cerrarlo.
                membership = struct.pack('IHH8s', socket.if_nametoindex(interface), 1, 0, b'')
                receiver.setsockopt(263, 1, membership)
                while not cancelled.is_set() and time.monotonic() - started < seconds:
                    try:
                        frame, ancillary, _flags, sender = receiver.recvmsg(65535, 1024)
                        if len(sender) > 2 and sender[2] == 4:  # PACKET_OUTGOING
                            continue
                        row, vlans = parse_frame(frame)
                        report['frames'] += 1
                        for level, kind, data in ancillary:
                            if level == 263 and kind == 8 and len(data) >= 20:
                                status = struct.unpack_from('I', data)[0]
                                if status & (1 << 4):  # TP_STATUS_VLAN_VALID
                                    vlans.append(struct.unpack_from('H', data, 16)[0] & 4095)
                        observed.update(vid for vid in vlans if 1 <= vid <= 4094)
                        if row:
                            key = (row['protocol'], row['source'], row['chassis'], row['port'])
                            if row['ttl'] == 0:
                                neighbors.pop(key, None)
                            elif key in neighbors or len(neighbors) < 128:
                                row['lastSeen'] = datetime.now().isoformat(timespec='seconds')
                                neighbors[key] = (time.monotonic() + row['ttl'], row)
                    except socket.timeout:
                        pass
                    now = time.monotonic()
                    neighbors = {key: value for key, value in neighbors.items() if value[0] > now}
                    if now - last_update >= 1:
                        report.update(elapsed=int(now - started), link=read_link(interface),
                                      neighbors=[value[1] for value in neighbors.values()], vlans=sorted(observed))
                        update(json.loads(json.dumps(report)))
                        last_update = now
        except PermissionError as exc:
            raise CommandFailedError(tr('switchPermission')) from exc
        except OSError as exc:
            raise CommandFailedError(tr('switchFailed', detail=str(exc))) from exc
        now = time.monotonic()
        report.update(elapsed=int(now - started), cancelled=cancelled.is_set(), link=read_link(interface),
                      neighbors=[value[1] for value in neighbors.values() if value[0] > now], vlans=sorted(observed))
        return report

    def save(self, report: dict) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        # La creación exclusiva evita pisar un informe guardado en el mismo segundo.
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        path = self.directory / f'puerto-{stamp}.json'
        with path.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        return path
