"""Servidor TFTP minimo (RFC 1350) para respaldar y entregar archivos a equipos de red.

Ignora las opciones de la RFC 2347 (blksize, tsize...): el cliente las descarta y usa bloques de 512.
"""
from __future__ import annotations

import argparse
import os
import socket
import struct
import sys
import threading

RRQ, WRQ, DATA, ACK, ERROR = 1, 2, 3, 4, 5
BLOCK = 512
TIMEOUT = 3.0
RETRIES = 5


def say(client: str, event: str) -> None:
    print(f'{client}\t{event}', flush=True)


def resolve(root: str, name: str) -> str | None:
    """Ruta dentro de `root`, o None si el nombre intenta salir de la carpeta."""
    base = os.path.realpath(root)
    relative = name.replace('\\', '/').lstrip('/')
    path = os.path.realpath(os.path.join(base, relative))
    if path == base or not path.startswith(base + os.sep):
        return None
    return path


def parse_request(data: bytes) -> tuple[int, str, str] | None:
    """Codigo de operacion, nombre y modo de un RRQ o WRQ."""
    if len(data) < 4:
        return None
    opcode = struct.unpack('!H', data[:2])[0]
    if opcode not in (RRQ, WRQ):
        return None
    parts = data[2:].split(b'\0')
    if len(parts) < 3 or not parts[0]:
        return None
    return opcode, parts[0].decode(errors='replace'), parts[1].decode(errors='replace').lower()


def error_packet(code: int, message: str) -> bytes:
    return struct.pack('!HH', ERROR, code) + message.encode() + b'\0'


def _wait(sock: socket.socket, peer: tuple, expect: int, block: int) -> bytes | None:
    """Espera ACK o DATA del bloque pedido. Ignora paquetes de otros origenes."""
    while True:
        try:
            data, origin = sock.recvfrom(BLOCK + 4)
        except socket.timeout:
            return None
        if origin != peer or len(data) < 4:
            continue
        opcode, number = struct.unpack('!HH', data[:4])
        if opcode == ERROR:
            raise ConnectionAbortedError(data[4:].rstrip(b'\0').decode(errors='replace') or 'error del cliente')
        if opcode == expect and number == block:
            return data


def _exchange(sock: socket.socket, peer: tuple, packet: bytes, expect: int, block: int) -> bytes:
    for _ in range(RETRIES):
        sock.sendto(packet, peer)
        reply = _wait(sock, peer, expect, block)
        if reply is not None:
            return reply
    raise TimeoutError('sin respuesta del cliente')


def send_file(sock: socket.socket, peer: tuple, path: str) -> int:
    total = 0
    block = 1
    with open(path, 'rb') as handle:
        while True:
            chunk = handle.read(BLOCK)
            _exchange(sock, peer, struct.pack('!HH', DATA, block) + chunk, ACK, block)
            total += len(chunk)
            if len(chunk) < BLOCK:
                return total
            block = (block + 1) & 0xFFFF


def receive_file(sock: socket.socket, peer: tuple, path: str) -> int:
    """Guarda en un archivo temporal y lo renombra al terminar: un corte no deja medio archivo."""
    partial = f'{path}.part'
    total = 0
    block = 0
    ack = struct.pack('!HH', ACK, 0)
    try:
        with open(partial, 'wb') as handle:
            while True:
                data = _exchange(sock, peer, ack, DATA, (block + 1) & 0xFFFF)
                block = (block + 1) & 0xFFFF
                payload = data[4:]
                handle.write(payload)
                total += len(payload)
                ack = struct.pack('!HH', ACK, block)
                if len(payload) < BLOCK:
                    sock.sendto(ack, peer)
                    break
        os.replace(partial, path)
    except BaseException:
        try:
            os.remove(partial)
        except OSError:
            pass
        raise
    return total


def handle(request: bytes, peer: tuple, host: str, root: str, writable: bool) -> None:
    client = peer[0]
    parsed = parse_request(request)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((host, 0))
        sock.settimeout(TIMEOUT)
        if parsed is None:
            sock.sendto(error_packet(4, 'Operacion no valida'), peer)
            return
        opcode, name, mode = parsed
        if mode not in ('octet', 'netascii'):
            sock.sendto(error_packet(4, 'Modo no soportado'), peer)
            say(client, f'Rechazado {name}: modo {mode}')
            return
        path = resolve(root, name)
        if path is None:
            sock.sendto(error_packet(2, 'Acceso denegado'), peer)
            say(client, f'Rechazado {name}: fuera de la carpeta')
            return
        try:
            if opcode == RRQ:
                if not os.path.isfile(path):
                    sock.sendto(error_packet(1, 'Archivo no encontrado'), peer)
                    say(client, f'No existe {name}')
                    return
                say(client, f'Envia {name}')
                size = send_file(sock, peer, path)
                say(client, f'Enviado {name} ({size} bytes)')
            else:
                if not writable:
                    sock.sendto(error_packet(2, 'Subidas deshabilitadas'), peer)
                    say(client, f'Rechazado {name}: subidas deshabilitadas')
                    return
                if os.path.isdir(path) or not os.path.isdir(os.path.dirname(path)):
                    sock.sendto(error_packet(2, 'Ruta no valida'), peer)
                    say(client, f'Rechazado {name}: ruta no valida')
                    return
                say(client, f'Recibe {name}')
                size = receive_file(sock, peer, path)
                say(client, f'Recibido {name} ({size} bytes)')
        except OSError as exc:
            sock.sendto(error_packet(3, 'Error de disco'), peer)
            say(client, f'Fallo {name}: {exc.strerror or exc}')
        except (TimeoutError, ConnectionAbortedError) as exc:
            say(client, f'Cortado {name}: {exc}')
    finally:
        sock.close()


def serve(host: str, port: int, root: str, writable: bool, ready: threading.Event | None = None,
          stop: threading.Event | None = None) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        server.bind((host, port))
    except OSError as exc:
        server.close()
        say('', f'No se pudo abrir el puerto {port}: {exc.strerror or exc}')
        raise SystemExit(1)
    server.settimeout(0.5)
    say('', f'TFTP escuchando en el puerto {server.getsockname()[1]}')
    if ready:
        ready.set()
    try:
        while not (stop and stop.is_set()):
            try:
                request, peer = server.recvfrom(BLOCK + 4)
            except socket.timeout:
                continue
            threading.Thread(target=handle, args=(request, peer, host, root, writable),
                             daemon=True).start()
    finally:
        server.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--port', type=int, default=69)
    parser.add_argument('--bind', default='')
    parser.add_argument('--writable', action='store_true')
    args = parser.parse_args(argv)
    os.makedirs(args.root, exist_ok=True)
    try:
        serve(args.bind, args.port, args.root, args.writable)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    main()
