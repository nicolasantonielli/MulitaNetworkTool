"""Servidor HTTP/HTTPS de prueba: pagina que confirma la conectividad, archivos y descargas.

    /            pagina de estado con la direccion del cliente
    /prueba/<n>  descarga de n MB para medir velocidad
    /archivos/   carpeta de archivos de prueba (tambien la raiz)
    /capturas/   capturas e informes de Mulita, solo lectura
"""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import posixpath
import secrets
import ssl
import sys
import threading
import time
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

if not __package__:  # The installer also launches this bundled program by path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mulita.servers.remote_page import CONTROL_PAGE, forward
from mulita.servers.web_pages import directory_content, home_content, render_page
from mulita.adapters.journals import FileJournalRepository
from mulita.adapters.settings_store import StoredSettingsReader
from mulita.core.events import OperationEvent
from mulita.core.event_payloads import OperationParameters, ExportReport
from mulita.presentation.journal import render_record
from mulita.presentation.journal_web import timeline
from mulita.core.settings import Settings
from mulita.core.storage import PLACES as STORAGE_PLACES
from mulita.core.journal_tests import PLACES as JOURNAL_PLACES
from mulita.services.journal import TechnicalJournalService

JOURNALS = {'actividad': ('Registro de actividades', '.log'), 'bitacora': ('Bitácora técnica', '.txt')}

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


def _file_size(entry: os.DirEntry) -> int | None:
    """Bytes de un archivo, o None para carpetas y archivos ilegibles."""
    if entry.is_dir():
        return None
    try:
        return entry.stat().st_size
    except OSError:
        return None


class Handler(SimpleHTTPRequestHandler):
    server_version = 'Mulita'
    secure = False

    def translate_path(self, path: str) -> str:
        return map_path(path, self.server.root, self.server.captures)

    def send_head(self):
        # Always show the file browser for folders, even if they contain index.html.
        path = self.translate_path(self.path)
        candidate = Path(path)
        if candidate.name.startswith('.mulita-') and candidate.suffix == '.lock':
            self.send_error(404)
            return None
        if self.server.captures and candidate.parent == Path(self.server.captures) / 'bitacora' and candidate.suffix == '.jsonl':
            self.send_error(404)
            return None
        if self.server.captures:
            for journal, (_title, suffix) in JOURNALS.items():
                folder = Path(self.server.captures) / journal
                if candidate.parent == folder and candidate.suffix == suffix:
                    # The raw file browser must use the same snapshot protocol
                    # as /bitacora/<day>/exportar, not stream a changing file.
                    try:
                        data = FileJournalRepository(folder, suffix).read_bytes(candidate.stem)
                    except (ValueError, FileNotFoundError):
                        self.send_error(404)
                        return None
                    except OSError:
                        self.send_error(403)
                        return None
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain; charset=utf-8')
                    self.send_header('Content-Length', str(len(data)))
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    snapshot = io.BytesIO(data)
                    snapshot.name = candidate.name
                    return snapshot
        if urlsplit(self.path).path.endswith('/') and os.path.isdir(path):
            return self.list_directory(path)
        return super().send_head()

    def _hidden(self, folder: str, item: os.DirEntry) -> bool:
        """Candados internos y el registro en bruto de la bitacora no se muestran."""
        if item.name.startswith('.mulita-') and item.name.endswith('.lock'):
            return True
        return bool(self.server.captures and Path(folder) == Path(self.server.captures) / 'bitacora'
                    and item.name.endswith('.jsonl'))

    def list_directory(self, path: str):
        try:
            with os.scandir(path) as listing:
                entries = sorted((item for item in listing if not self._hidden(path, item)),
                                 key=lambda item: (not item.is_dir(), item.name.casefold()))
        except OSError:
            self.send_error(403, 'No se puede acceder a esta carpeta.')
            return None
        parts = [part for part in unquote(urlsplit(self.path).path).split('/')
                 if part and part not in ('.', '..')]
        content = directory_content(parts, [(item.name, item.is_dir(), _file_size(item)) for item in entries])
        page = render_page(content, self.secure)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(page)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        return io.BytesIO(page)

    def send_error(self, code, message=None, explain=None):
        content = (
            '<p class="eyebrow">Servidor web</p><h1>Error ERROR_CODE</h1>'
            '<p class="intro">No se pudo completar la solicitud.</p>'
            '<section class="panel connection"><h2>ERROR_MESSAGE</h2>'
            '<p>Comprobá la dirección o volvé al inicio para explorar los recursos disponibles.</p>'
            '<a class="back-link" href="/">← Volver al inicio</a></section>')
        # The standard handler escapes the message and preserves HTTP/HEAD semantics.
        self.error_message_format = (render_page(content, self.secure).decode('utf-8')
                                     .replace('%', '%%').replace('ERROR_CODE', '%(code)d')
                                     .replace('ERROR_MESSAGE', '%(message)s'))
        if message == 'File not found':
            message = 'No se encontró el archivo o la carpeta.'
        super().send_error(code, message, explain)

    def log_request(self, code='-', size='-') -> None:
        if code in (200, 202) and self.path in ('/control/frame', '/control/input'):
            return
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
        if path.rstrip('/') == '/control':
            self._send_data(render_page(CONTROL_PAGE, self.secure), 'text/html; charset=utf-8', send_body)
            return True
        if path.partition('/')[2].partition('/')[0] in JOURNALS:
            self._activity(path, send_body)
            return True
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

    def _activity(self, path: str, send_body: bool) -> None:
        if not self.server.captures:
            self.send_error(404)
            return
        journal = path.split('/')[1]
        title, suffix = JOURNALS[journal]
        repository = FileJournalRepository(Path(self.server.captures) / journal, suffix)
        try:
            if path.rstrip('/') == '/' + journal:
                rows = ''.join(
                    f'<li><a class="resource" href="/{journal}/{day}">{day}</a></li>'
                    for day in repository.days())
                content = f'<h1>{title}</h1>' + (
                    f'<ul class="panel file-list">{rows}</ul>' if rows else
                    '<p class="empty">Todavía no hay jornadas registradas.</p>')
            else:
                parts = path.removeprefix(f'/{journal}/').rstrip('/').split('/')
                day = parts[0]
                filename = day + suffix
                if journal == 'bitacora' and parts == [day, 'exportar.csv']:
                    filename = day + '.csv'
                    self._send_data(repository.csv_bytes(day), 'text/csv; charset=utf-8', send_body, filename)
                    if send_body:
                        self._export_note(filename)
                    return
                if parts == [day, 'exportar']:
                    data = repository.read_bytes(day)
                    self._send_data(data, 'text/plain; charset=utf-8', send_body, filename)
                    if send_body:
                        self._export_note(filename)
                    return
                if parts != [day]:
                    raise FileNotFoundError
                report = html.escape(repository.read_bytes(day).decode('utf-8'))
                body = f'<pre class="panel connection journal">{report}</pre>'
                csv_link = ''
                if journal == 'bitacora':
                    settings = (StoredSettingsReader(Path(self.server.journal_settings)).current
                                if self.server.journal_settings else Settings())
                    body = timeline(repository.read_entries(day), settings)
                    csv_link = f'<a class="download" href="/{journal}/{day}/exportar.csv">Exportar CSV</a>'
                content = (
                    f'<a class="back-link" href="/{journal}/">← Todas las jornadas</a>'
                    f'<h1>{title} · {day}</h1><div class="journal-actions">'
                    f'<a class="download" href="/{journal}/{day}/exportar">Exportar {suffix}</a>'
                    f'{csv_link}'
                    f'<form method="post" action="/{journal}/{day}/eliminar" '
                    f'onsubmit="return confirm(\'¿Eliminar el registro del {day}?\')">'
                    f'<input type="hidden" name="token" value="{self.server.activity_token}">'
                    '<button type="submit" class="theme">Eliminar jornada</button></form></div>'
                    f'{body}')
            self._send_data(render_page(content, self.secure), 'text/html; charset=utf-8', send_body)
        except (FileNotFoundError, ValueError):
            self.send_error(404)
        except OSError:
            self.send_error(403)

    def copyfile(self, source, outputfile):
        super().copyfile(source, outputfile)
        if self.server.captures and self.path.startswith('/capturas/') and hasattr(source, 'name'):
            path = Path(self.translate_path(self.path))
            relative = path.relative_to(Path(self.server.captures))
            test = None
            if len(relative.parts) == 1 and path.suffix == '.pcap':
                test = 'capture'
            elif len(relative.parts) > 1:
                test = next((JOURNAL_PLACES.get(place.id) for place in STORAGE_PLACES
                             if place.folder == relative.parts[0]), None)
            self._export_note(Path(source.name).name, test)

    def _export_note(self, name, test=None):
        if not self.server.journal_settings:
            return
        service = TechnicalJournalService(
            StoredSettingsReader(Path(self.server.journal_settings)), render_record,
            FileJournalRepository(Path(self.server.captures) / 'bitacora', '.txt').append)
        service.record(OperationEvent('web_export', 'completed', OperationParameters(test=test or ''), ExportReport((name,))))

    def do_POST(self) -> None:
        parts = urlsplit(self.path).path.split('/')
        if len(parts) == 3 and parts[1] == 'control':
            self._remote(parts[2])
            return
        if not self.server.captures or len(parts) != 4 or parts[1] not in JOURNALS or parts[3] != 'eliminar':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 256 or self.headers.get_content_type() != 'application/x-www-form-urlencoded':
                self.send_error(400)
                return
            form = parse_qs(self.rfile.read(length).decode('ascii'))
            if form.get('token') != [self.server.activity_token]:
                self.send_error(403)
                return
            FileJournalRepository(Path(self.server.captures) / parts[1], JOURNALS[parts[1]][1]).delete(
                parts[2], missing_ok=False)
        except (ValueError, FileNotFoundError):
            self.send_error(404)
            return
        except OSError:
            self.send_error(403)
            return
        self.send_response(303)
        self.send_header('Location', f'/{parts[1]}/')
        self.end_headers()

    def _remote(self, action):
        if action not in ('pair', 'frame', 'input', 'end'):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 512 or self.headers.get_content_type() != 'application/json':
                self.send_error(400)
                return
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError
        except (ValueError, UnicodeError):
            self.send_error(400)
            return
        data['action'] = action
        data['token'] = self.headers.get('Authorization', '').removeprefix('Bearer ')[:64]
        code, body = forward(data)
        self._send_data(body, 'image/jpeg' if action == 'frame' else 'text/plain', True, status=code)

    def _index(self, send_body: bool) -> None:
        content = home_content(
            'HTTPS' if self.secure else 'HTTP', self.client_address[0],
            self.connection.getsockname()[0], time.strftime('%Y-%m-%d %H:%M:%S'),
            bool(self.server.captures), bool(os.environ.get('MULITA_CONTROL_PORT')))
        self._send_data(render_page(content, self.secure), 'text/html; charset=utf-8', send_body)

    def _send_data(self, page, content_type, send_body, filename=None, status=200):
        self.send_response(status)
        if self.path.split('?', 1)[0].rstrip('/') == '/control':
            self.send_header('Content-Security-Policy', "frame-ancestors 'none'")
            self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Content-Type', content_type)
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
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
        self.journal_settings = None
        self.activity_token = secrets.token_urlsafe(32)
        self.context = context
        super().__init__(address, handler)

    def handle_error(self, request, client_address) -> None:
        error = sys.exc_info()[1]
        say(client_address[0], f'Conexion fallida: {error}')


def serve(host: str, http_port: int, https_port: int, root: str, captures: str, cert: str, key: str,
          ready: threading.Event | None = None, journal_settings=None) -> list[Server]:
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
    for server in servers:
        server.journal_settings = journal_settings
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
    parser.add_argument('--journal-settings')
    args = parser.parse_args(argv)
    os.makedirs(args.root, exist_ok=True)
    if not args.http_port and not args.https_port:
        say('', 'Ningun puerto elegido')
        sys.exit(1)
    servers = serve(args.bind, args.http_port, args.https_port, args.root, args.captures,
                    args.cert, args.key, journal_settings=args.journal_settings)
    try:
        servers[0].serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    main()
