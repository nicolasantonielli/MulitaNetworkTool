"""Servidor SNTP minimo: responde con la hora del sistema de Mulita.

La precision es la del reloj de Mulita. El estrato que anuncia se elige a mano.
"""
from __future__ import annotations

import argparse
import socket
import struct
import sys
import threading
import time

NTP_EPOCH = 2208988800
PACKET = 48
CLIENT_MODE = 3
SERVER_MODE = 4


def say(client: str, event: str) -> None:
    print(f'{client}\t{event}', flush=True)


def timestamp(seconds: float) -> bytes:
    whole = int(seconds)
    return struct.pack('!II', whole + NTP_EPOCH, int((seconds - whole) * 2 ** 32))


def build_reply(request: bytes, received: float, stratum: int, transmit: float | None = None) -> bytes | None:
    """Respuesta a un paquete de cliente, o None si no lo es."""
    if len(request) < PACKET or request[0] & 7 != CLIENT_MODE:
        return None
    version = (request[0] >> 3) & 7
    if not 1 <= version <= 4:
        version = 4
    header = struct.pack('!BBBbII4s', (version << 3) | SERVER_MODE, stratum, request[2], -20,
                         0, 0x00000100, b'LOCL')
    sent = time.time() if transmit is None else transmit
    # Referencia y recepcion: ahora. Origen: el transmit del cliente, para que valide la respuesta.
    return header + timestamp(received) + request[40:48] + timestamp(received) + timestamp(sent)


def serve(host: str, port: int, stratum: int, ready: threading.Event | None = None,
          stop: threading.Event | None = None) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        server.bind((host, port))
    except OSError as exc:
        server.close()
        say('', f'No se pudo abrir el puerto {port}: {exc.strerror or exc}')
        raise SystemExit(1)
    server.settimeout(0.5)
    say('', f'NTP escuchando en el puerto {server.getsockname()[1]} (estrato {stratum})')
    if ready:
        ready.set()
    try:
        while not (stop and stop.is_set()):
            try:
                request, peer = server.recvfrom(1024)
            except socket.timeout:
                continue
            received = time.time()
            reply = build_reply(request, received, stratum)
            if reply is None:
                continue
            server.sendto(reply, peer)
            say(peer[0], f'Hora entregada (NTPv{(request[0] >> 3) & 7})')
    finally:
        server.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=123)
    parser.add_argument('--bind', default='')
    parser.add_argument('--stratum', type=int, default=3)
    args = parser.parse_args(argv)
    try:
        serve(args.bind, args.port, args.stratum)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    main()
