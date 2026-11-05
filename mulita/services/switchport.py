"""Identificación de la boca conectada, sin modificar IP ni configuración del switch."""
from __future__ import annotations

from mulita.core.events import EventSource
from mulita.services.operation_events import operation

import json
import threading
import time
from datetime import datetime
from pathlib import Path

from mulita.core import validation
from mulita.core.platform import PacketSource, LinkReader, SwitchReportStore
from mulita.core.switchport import parse_frame
from mulita.core.messages import message


class SwitchPortService(EventSource):
    def __init__(self, packets: PacketSource, link: LinkReader, reports: SwitchReportStore):
        self._packets = packets
        self._link = link
        self._reports = reports
        self.cancelled = threading.Event()

    def stop(self) -> None:
        self.cancelled.set()

    @operation('switch', 'interface')
    def scan(self, interface: str, seconds: int, cancelled: threading.Event,
             update, simulated: bool = False) -> dict:
        interface = validation.interface_name(interface)
        seconds = validation.integer_between(str(seconds), 5, 180, message('switchDuration'))
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
        neighbors: dict[tuple, tuple[float, dict]] = {}
        observed: set[int] = set()
        last_update = -1.0
        with self._packets.open(interface) as receiver:
            while not cancelled.is_set() and time.monotonic() - started < seconds:
                packet = receiver.receive()
                if packet is not None:
                    row, vlans = parse_frame(packet.data)
                    report['frames'] += 1
                    vlans.extend(packet.vlans)
                    observed.update(vid for vid in vlans if 1 <= vid <= 4094)
                    if row:
                        key = (row['protocol'], row['source'], row['chassis'], row['port'])
                        if row['ttl'] == 0:
                            neighbors.pop(key, None)
                        elif key in neighbors or len(neighbors) < 128:
                            row['lastSeen'] = datetime.now().isoformat(timespec='seconds')
                            neighbors[key] = (time.monotonic() + row['ttl'], row)
                now = time.monotonic()
                neighbors = {key: value for key, value in neighbors.items() if value[0] > now}
                if now - last_update >= 1:
                    report.update(elapsed=int(now - started), link=self._link.read(interface),
                                  neighbors=[value[1] for value in neighbors.values()], vlans=sorted(observed))
                    update(json.loads(json.dumps(report)))
                    last_update = now
        now = time.monotonic()
        report.update(elapsed=int(now - started), cancelled=cancelled.is_set(), link=self._link.read(interface),
                      neighbors=[value[1] for value in neighbors.values() if value[0] > now], vlans=sorted(observed))
        return report

    @operation('export')
    def save(self, report: dict) -> Path:
        return self._reports.save(report)
