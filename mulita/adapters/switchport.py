"""Recepción Ethernet, lectura sysfs y almacenamiento de informes."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import json
import socket
import struct
from mulita.core.platform import ReceivedFrame
from mulita.core.errors import CommandFailedError
from mulita.core.messages import message

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


class LinuxPacketSource:
    def __init__(self, socket_api=socket):
        self._socket = socket_api

    @contextmanager
    def open(self, interface: str):
        api = self._socket
        if not hasattr(api, 'AF_PACKET'):
            raise CommandFailedError(message('switchLinux'))
        try:
            with api.socket(api.AF_PACKET, api.SOCK_RAW, api.htons(3)) as receiver:
                receiver.bind((interface, 0))
                receiver.settimeout(0.25)
                # AUXDATA conserva las etiquetas VLAN quitadas por offload.
                receiver.setsockopt(263, 8, 1)
                membership = struct.pack('IHH8s', api.if_nametoindex(interface), 1, 0, b'')
                receiver.setsockopt(263, 1, membership)
                yield _SocketReceiver(receiver)
        except PermissionError as exc:
            raise CommandFailedError(message('switchPermission')) from exc
        except OSError as exc:
            raise CommandFailedError(message('switchFailed', detail=str(exc))) from exc


class _SocketReceiver:
    def __init__(self, receiver):
        self._receiver = receiver

    def receive(self) -> ReceivedFrame | None:
        try:
            frame, ancillary, _flags, sender = self._receiver.recvmsg(65535, 1024)
        except socket.timeout:
            return None
        if len(sender) > 2 and sender[2] == 4:  # PACKET_OUTGOING
            return None
        vlans = []
        for level, kind, data in ancillary:
            if level == 263 and kind == 8 and len(data) >= 20:
                status = struct.unpack_from('I', data)[0]
                if status & (1 << 4):  # TP_STATUS_VLAN_VALID
                    vlans.append(struct.unpack_from('H', data, 16)[0] & 4095)
        return ReceivedFrame(frame, tuple(vlans))


class SysfsLinkReader:
    def __init__(self, root: Path = Path('/sys/class/net')):
        self._root = root

    def read(self, interface: str) -> dict:
        return read_link(interface, self._root)


class JsonSwitchReportStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def save(self, report: dict) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        # La creación exclusiva evita pisar un informe guardado en el mismo segundo.
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        path = self.directory / f'puerto-{stamp}.json'
        with path.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        return path
