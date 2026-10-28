"""Servidor HTTP/HTTPS de prueba: pagina que confirma la conectividad, archivos y descargas.

    /            pagina de estado con la direccion del cliente
    /prueba/<n>  descarga de n MB para medir velocidad
    /archivos/   carpeta de archivos de prueba (tambien la raiz)
    /capturas/   capturas e informes de Mulita, solo lectura
"""
from __future__ import annotations

import argparse
import html
import os
import posixpath
import socket
import ssl
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

MAX_TEST_MB = 1024
CHUNK = 64 * 1024


def say(client: str, event: str) -> None:
    print(f'{client}\t{event}', flush=True)


def map_path(url_path: str, root: str, captures: str) -> str:
    """Archivo local de una URL. Descarta `..` y puntos para no salir de las carpetas."""
    parts = [part for part in posixpath.normpath(unquote(urlsplit(url_path).path)).split('/')
             if part and part not in ('.', '..')]
    base = root
    if parts and parts[0] == 'capturas' and captures:
        base, parts = captures, parts[1:]
    elif parts and parts[0] == 'archivos':
        parts = parts[1:]
    return os.path.join(base, *parts)


def test_size(url_path: str) -> int | None:
    """Bytes de `/prueba/<n>`, o None si la ruta no es una descarga de prueba."""
    parts = [part for part in urlsplit(url_path).path.split('/') if part]
    if len(parts) != 2 or parts[0] != 'prueba' or not parts[1].isdigit():
        return None
    return max(1, min(int(parts[1]), MAX_TEST_MB)) * 1024 * 1024


class Handler(SimpleHTTPRequestHandler):
    server_version = 'Mulita'
    secure = False

    def translate_path(self, path: str) -> str:
        return map_path(path, self.server.root, self.server.captures)

    def log_request(self, code='-', size='-') -> None:
        say(self.client_address[0], f'{self.command} {self.path} {code}')

    def log_message(self, format, *args) -> None:  # noqa: A002
        say(self.client_address[0], format % args)

    def do_GET(self) -> None:
        if not self._special(send_body=True):
            super().do_GET()

    def do_HEAD(self) -> None:
        if not self._special(send_body=False):
            super().do_HEAD()

    def _special(self, send_body: bool) -> bool:
        path = urlsplit(self.path).path
        if path in ('/', ''):
            self._index(send_body)
            return True
        size = test_size(path)
        if size is None:
            return False
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(size))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if send_body:
            block = b'\0' * CHUNK
            remaining = size
            try:
                while remaining > 0:
                    sent = min(CHUNK, remaining)
                    self.wfile.write(block[:sent])
                    remaining -= sent
            except (BrokenPipeError, ConnectionResetError):
                pass
        return True

    def _index(self, send_body: bool) -> None:
        server = self.connection.getsockname()[0]
        scheme = 'HTTPS' if self.secure else 'HTTP'
        links = ['<li><a href="/archivos/">Archivos de prueba</a></li>']
        if self.server.captures:
            links.append('<li><a href="/capturas/">Capturas e informes</a></li>')
        links += [f'<li><a href="/prueba/{mb}">Descarga de {mb} MB</a></li>' for mb in (1, 10, 100)]
        page = (
            '<!doctype html><html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Mulita</title><style>body{font-family:sans-serif;max-width:34em;margin:2em auto;'
            'padding:0 1em;color:#1b2430}h1{color:#1c8f4c}code{background:#eef1f5;padding:.1em .4em}'
            '</style></head><body>'
            f'<h1>Conexion establecida</h1><p>Este equipo llego a Mulita por {scheme}.</p>'
            f'<p>Su direccion: <code>{html.escape(self.client_address[0])}</code><br>'
            f'Servidor: <code>{html.escape(server)}</code><br>'
            f'Hora: <code>{time.strftime("%Y-%m-%d %H:%M:%S")}</code></p>'
            f'<ul>{"".join(links)}</ul></body></html>').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(page)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if send_body:
            self.wfile.write(page)


class SecureHandler(Handler):
    secure = True

    def setup(self) -> None:
        # El saludo TLS se hace en el hilo de la conexion: un cliente lento no frena a los demas.
        self.request.settimeout(10)
        self.request = self.server.context.wrap_socket(self.request, server_side=True)
        super().setup()

    def finish(self) -> None:
        # wrap_socket separa el socket original: nadie mas cerraria el cifrado.
        try:
            super().finish()
        finally:
            self.request.close()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple, handler, root: str, captures: str,
                 context: ssl.SSLContext | None = None):
        self.root = root
        self.captures = captures
        self.context = context
        super().__init__(address, handler)

    def handle_error(self, request, client_address) -> None:
        error = sys.exc_info()[1]
        say(client_address[0], f'Conexion fallida: {error}')


def serve(host: str, http_port: int, https_port: int, root: str, captures: str, cert: str, key: str,
          ready: threading.Event | None = None) -> list[Server]:
    servers: list[Server] = []
    try:
        if http_port:
            servers.append(Server((host, http_port), Handler, root, captures))
            say('', f'HTTP escuchando en el puerto {servers[-1].server_address[1]}')
        if https_port:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            servers.append(Server((host, https_port), SecureHandler, root, captures, context))
            say('', f'HTTPS escuchando en el puerto {servers[-1].server_address[1]}')
    except (OSError, ssl.SSLError) as exc:
        for opened in servers:
            opened.server_close()
        say('', f'No se pudo iniciar el servidor web: {getattr(exc, "strerror", None) or exc}')
        raise SystemExit(1)
    for extra in servers[1:]:
        threading.Thread(target=extra.serve_forever, daemon=True).start()
    if ready:
        ready.set()
    return servers


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--captures', default='')
    parser.add_argument('--bind', default='')
    parser.add_argument('--http-port', type=int, default=80)
    parser.add_argument('--https-port', type=int, default=0)
    parser.add_argument('--cert', default='')
    parser.add_argument('--key', default='')
    args = parser.parse_args(argv)
    os.makedirs(args.root, exist_ok=True)
    if not args.http_port and not args.https_port:
        say('', 'Ningun puerto elegido')
        sys.exit(1)
    servers = serve(args.bind, args.http_port, args.https_port, args.root, args.captures,
                    args.cert, args.key)
    try:
        servers[0].serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    main()
