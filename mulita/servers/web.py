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
import socket
import ssl
import sys
import threading
import time
from string import Template
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlsplit

if not __package__:  # The installer also launches this bundled program by path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mulita.servers.remote_page import CONTROL_PAGE, forward
from mulita.adapters.journals import FileJournalRepository
from mulita.adapters.settings_store import StoredSettingsReader
from mulita.core.events import OperationEvent
from mulita.presentation.journal import render_record
from mulita.presentation.journal_web import timeline
from mulita.core.settings import Settings
from mulita.core.storage import PLACES as STORAGE_PLACES
from mulita.core.journal_tests import PLACES as JOURNAL_PLACES
from mulita.services.journal import TechnicalJournalService

JOURNALS = {'actividad': ('Registro de actividades', '.log'), 'bitacora': ('Bitácora técnica', '.txt')}

MAX_TEST_MB = 1024
CHUNK = 64 * 1024

# Inline assets keep this standalone server usable without Qt or internet access.
PAGE = '''<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Mulita · Servidor web</title>
<script>
try { const theme = localStorage.getItem('mulita-theme');
  if (theme === 'dark' || theme === 'light') document.documentElement.dataset.theme = theme;
} catch (_) {}
</script>
<style>
:root { color-scheme: light; --bg:#EEF2F6; --surface:#FFFFFF; --alt:#F3F6F9;
  --high:#E2E8EF; --border:#D3DBE4; --text:#17212B; --muted:#5D6B7A;
  --primary:#0B76DA; --success:#15935B; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { color-scheme:dark; --bg:#0E1319; --surface:#161D26;
    --alt:#1E2733; --high:#283443; --border:#2C3948; --text:#E6EDF3;
    --muted:#8A98A8; --primary:#2E9BFF; --success:#22B573; }
}
:root[data-theme="dark"] { color-scheme:dark; --bg:#0E1319; --surface:#161D26;
  --alt:#1E2733; --high:#283443; --border:#2C3948; --text:#E6EDF3;
  --muted:#8A98A8; --primary:#2E9BFF; --success:#22B573; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text);
  font:15px/1.6 "Segoe UI",system-ui,sans-serif; }
a { color:var(--primary); text-decoration:none; }
button { font:inherit; cursor:pointer; }
a:focus-visible,button:focus-visible { outline:3px solid var(--primary); outline-offset:4px; }
.topbar { background:var(--surface); border-bottom:1px solid var(--border); }
.bar { max-width:1080px; margin:auto; padding:18px 28px; display:flex;
  align-items:center; justify-content:space-between; gap:20px; }
.brand { display:flex; align-items:center; gap:12px; color:var(--text); }
.mark { display:grid; place-items:center; width:42px; height:42px;
  border-radius:12px; background:var(--alt); color:var(--primary); }
svg { width:24px; height:24px; fill:none; stroke:currentColor; stroke-width:1.7;
  stroke-linecap:round; stroke-linejoin:round; }
.brand strong { display:block; font-size:20px; line-height:1.2; letter-spacing:-.5px; }
.brand small { color:var(--muted); font-size:12px; }
.theme { display:flex; align-items:center; gap:9px; border:1px solid var(--border);
  border-radius:9px; padding:9px 13px; min-height:44px; background:var(--alt); color:var(--text); }
[hidden] { display:none !important; }
.breadcrumbs { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:20px; overflow-wrap:anywhere; }
.file-list { margin:0; padding:0; list-style:none; overflow:hidden; }
.file-list li + li { border-top:1px solid var(--border); }
.file-list .resource { min-width:0; }
.file-name { min-width:0; overflow-wrap:anywhere; }
.empty { padding:28px; color:var(--muted); }
.back-link { display:inline-flex; align-items:center; min-height:44px; margin-top:12px; }
.journal { white-space:pre-wrap; overflow-wrap:anywhere; font:14px/1.6 Consolas,monospace; }
.journal-actions { display:flex; flex-wrap:wrap; align-items:center; gap:18px; margin:16px 0; }
.theme:hover { background:var(--high); }
main { max-width:1080px; margin:auto; padding:42px 28px 28px; }
.eyebrow { margin:0 0 8px; color:var(--muted); font-size:12px; font-weight:600;
  letter-spacing:1.6px; text-transform:uppercase; }
h1 { margin:0; font-size:clamp(28px,4vw,38px); line-height:1.2; letter-spacing:-1px; }
.intro { margin:10px 0 26px; color:var(--muted); }
.panel { background:var(--surface); border:1px solid var(--border); border-radius:14px; }
.connection { padding:24px; }
.panel-heading { display:flex; align-items:center; justify-content:space-between; gap:16px; }
h2 { font-size:17px; margin:0; font-weight:600; }
.badge { display:inline-flex; align-items:center; gap:8px; color:var(--success);
  font-size:13px; font-weight:600; white-space:nowrap; }
.dot { width:8px; height:8px; border-radius:50%; background:var(--success); }
dl { display:grid; grid-template-columns:1fr 1fr 1.2fr; gap:16px; margin:22px 0 0; }
dl div { background:var(--alt); padding:16px; border-radius:9px; min-width:0; }
dt { color:var(--muted); font-size:12px; margin-bottom:6px; }
dd { margin:0; font:14px/1.6 Consolas,monospace; overflow-wrap:anywhere; }
.section-title { margin:30px 0 14px; }
.resources { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:16px; }
.resource { padding:22px; display:flex; align-items:center; gap:16px; color:var(--text); }
.resource:hover { border-color:var(--primary); background:var(--alt); }
.resource .mark { flex-shrink:0; }
.resource strong { display:block; font-size:15px; font-weight:600; }
.resource small { display:block; color:var(--muted); margin-top:3px; }
.arrow { margin-left:auto; color:var(--primary); font-size:22px; }
.downloads { margin-top:24px; padding:24px; }
.downloads p { margin:6px 0 20px; color:var(--muted); font-size:14px; }
.sizes { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
.download { display:flex; align-items:center; justify-content:space-between; gap:12px;
  background:var(--alt); border:1px solid var(--border); border-radius:9px; padding:14px 18px; }
.download:hover { background:var(--high); border-color:var(--primary); }
.download strong { display:block; font-size:20px; color:var(--text); }
.download small { font-size:12px; color:var(--muted); }
footer { display:flex; justify-content:space-between; gap:12px; margin-top:24px;
  color:var(--muted); font-size:12px; }
@media (max-width:600px) {
  .bar { padding:16px; } main { padding:28px 16px 20px; }
  .connection,.downloads { padding:18px; } dl { grid-template-columns:1fr; gap:8px; }
  dl div { padding:12px; } .sizes { grid-template-columns:1fr; }
  .download { padding:12px 16px; } footer { flex-direction:column; gap:4px; }
}
</style></head><body>
<header class="topbar"><div class="bar">
<a class="brand" href="/" aria-label="Mulita, inicio"><span class="mark" aria-hidden="true">
<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="7" rx="2"/>
<rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.01M7 17.5h.01M12 6.5h5M12 17.5h5"/></svg>
</span><span><strong>Mulita</strong><small>Network tools</small></span></a>
<button class="theme" id="theme" type="button" hidden>
<svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/>
<path d="M12 4v16M12 4a8 8 0 0 1 0 16Z"/></svg><span id="theme-label">Modo oscuro</span></button>
</div></header>
<main>$content
<footer><span>Mulita · Herramientas de diagnóstico de red</span><span>Conexión por $scheme</span></footer>
</main><script>
const button = document.getElementById('theme');
const preference = window.matchMedia('(prefers-color-scheme: dark)');
function isDark() { return document.documentElement.dataset.theme
  ? document.documentElement.dataset.theme === 'dark' : preference.matches; }
function updateLabel() {
  const label = isDark() ? 'Modo claro' : 'Modo oscuro';
  document.getElementById('theme-label').textContent = label;
  button.setAttribute('aria-label', 'Cambiar a ' + label.toLowerCase());
}
button.hidden = false;
button.addEventListener('click', function () {
  const theme = isDark() ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('mulita-theme', theme); } catch (_) {}
  updateLabel();
});
if (preference.addEventListener) preference.addEventListener('change', updateLabel);
updateLabel();
</script></body></html>'''


HOME = '''<p class="eyebrow">Servidor web · $scheme</p>
<h1>Conexión establecida</h1><p class="intro">Este equipo llegó a Mulita por $scheme.</p>
<section class="panel connection" aria-labelledby="connection-title">
<div class="panel-heading"><h2 id="connection-title">Tu conexión</h2>
<span class="badge"><span class="dot"></span>Acceso confirmado</span></div>
<dl><div><dt>Tu dirección IP</dt><dd>$client</dd></div>
<div><dt>Dirección del servidor</dt><dd>$server</dd></div>
<div><dt>Hora del servidor al cargar</dt><dd>$timestamp</dd></div></dl></section>
<h2 class="section-title">Recursos compartidos</h2><div class="resources">
<a class="panel resource" href="/archivos/"><span class="mark" aria-hidden="true">
<svg viewBox="0 0 24 24"><path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/></svg>
</span><span><strong>Archivos de prueba</strong><small>Explorá y descargá archivos del servidor.</small></span>
<span class="arrow" aria-hidden="true">›</span></a>$captures</div>
<section class="panel downloads" aria-labelledby="downloads-title">
<h2 id="downloads-title">Probá la transferencia</h2>
<p>Descargá un archivo de prueba para comprobar la transferencia de datos en tu red.</p>
<div class="sizes">$downloads</div></section>
'''


def render_page(content: str, secure: bool = False) -> bytes:
    """One shared shell for the home page, folders and HTTP errors."""
    return Template(PAGE).substitute(
        content=content, scheme='HTTPS' if secure else 'HTTP').encode('utf-8')


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

    def list_directory(self, path: str):
        try:
            with os.scandir(path) as listing:
                entries = sorted((item for item in listing if not (
                    (item.name.startswith('.mulita-') and item.name.endswith('.lock')) or
                    (self.server.captures and Path(path) == Path(self.server.captures) / 'bitacora' and item.name.endswith('.jsonl')))),
                    key=lambda item: (not item.is_dir(), item.name.casefold()))
        except OSError:
            self.send_error(403, 'No se puede acceder a esta carpeta.')
            return None

        parts = [part for part in unquote(urlsplit(self.path).path).split('/')
                 if part and part not in ('.', '..')]
        labels = {'archivos': 'Archivos de prueba', 'capturas': 'Capturas e informes'}
        title = labels.get(parts[0], parts[0]) if len(parts) == 1 else (parts[-1] if parts else 'Archivos')
        crumbs = ['<a href="/">Inicio</a>']
        for index, part in enumerate(parts):
            label = labels.get(part, part) if index == 0 else part
            href = '/' + '/'.join(quote(piece, safe='') for piece in parts[:index + 1]) + '/'
            crumbs.append(f'<span aria-hidden="true">/</span><a href="{href}">{html.escape(label)}</a>')
        parent = '/' + '/'.join(quote(piece, safe='') for piece in parts[:-1])
        if parent != '/':
            parent += '/'
        rows = []
        for entry in entries:
            folder = entry.is_dir()
            href = quote(entry.name, safe='') + ('/' if folder else '')
            label = html.escape(entry.name)
            if folder:
                detail = 'Carpeta · Abrir'
                icon = '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>'
            else:
                try:
                    size = entry.stat().st_size
                    detail = f'{size:,} bytes · Descargar'.replace(',', '.')
                except OSError:
                    detail = 'Archivo · Descargar'
                icon = '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9ZM14 3v6h6M8 13h8M8 17h5"/>'
            download = '' if folder else ' download'
            rows.append(
                f'<li><a class="resource" href="{href}"{download}>'
                f'<span class="mark" aria-hidden="true"><svg viewBox="0 0 24 24">{icon}</svg></span>'
                f'<span class="file-name"><strong>{label}</strong><small>{detail}</small></span>'
                '<span class="arrow" aria-hidden="true">›</span></a></li>')
        listing = ('<ul class="panel file-list">' + ''.join(rows) + '</ul>' if rows else
                   '<div class="panel empty">Esta carpeta está vacía.</div>')
        content = (
            '<nav class="breadcrumbs" aria-label="Ruta de navegación">' + ''.join(crumbs) + '</nav>'
            f'<p class="eyebrow">Recursos compartidos</p><h1>{html.escape(title)}</h1>'
            f'<p class="intro">{len(entries)} elementos · Explorá las carpetas o descargá un archivo.</p>'
            + listing + f'<a class="back-link" href="{parent}">← Volver al nivel anterior</a>')
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
        service.record(OperationEvent('web_export', 'completed', {'test': test}, name))

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
        server = self.connection.getsockname()[0]
        scheme = 'HTTPS' if self.secure else 'HTTP'
        captures = ''
        if self.server.captures:
            captures = (
                '<a class="panel resource" href="/capturas/">'
                '<span class="mark" aria-hidden="true"><svg viewBox="0 0 24 24">'
                '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/>'
                '<path d="M14 3v6h6M8 13h8M8 17h5"/></svg></span>'
                '<span><strong>Capturas e informes</strong>'
                '<small>Consultá los resultados de Mulita.</small></span>'
                '<span class="arrow" aria-hidden="true">›</span></a>')
            captures += ('<a class="panel resource" href="/actividad/"><span><strong>Registro de actividades</strong>'
                         '<small>Consultar jornadas y exportar registros.</small></span>'
                         '<span class="arrow" aria-hidden="true">›</span></a>')
            captures += ('<a class="panel resource" href="/bitacora/"><span><strong>Bitácora técnica</strong>'
                         '<small>Acciones, resultados y archivos exportados por jornada.</small></span>'
                         '<span class="arrow" aria-hidden="true">›</span></a>')
        downloads = ''.join(
            f'<a class="download" href="/prueba/{mb}" download="mulita-prueba-{mb}MB.bin">'
            f'<span><strong>{mb} MB</strong><small>Descargar archivo</small></span>'
            '<svg aria-hidden="true" viewBox="0 0 24 24">'
            '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></svg></a>'
            for mb in (1, 10, 100))
        if os.environ.get('MULITA_CONTROL_PORT'):
            captures += ('<a class="panel resource" href="/control"><strong>Control remoto</strong>'
                         '<span class="arrow" aria-hidden="true">›</span></a>')
        content = Template(HOME).substitute(
            scheme=scheme, client=html.escape(self.client_address[0]),
            server=html.escape(server), timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
            captures=captures, downloads=downloads)
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
