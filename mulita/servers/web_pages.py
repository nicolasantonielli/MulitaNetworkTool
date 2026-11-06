"""Paginas HTML del servidor web: plantillas y constructores de contenido, sin acceso a red ni disco."""
from __future__ import annotations

import html
from string import Template
from urllib.parse import quote

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


FOLDER_ICON = '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>'
FILE_ICON = '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9ZM14 3v6h6M8 13h8M8 17h5"/>'
SECTION_LABELS = {'archivos': 'Archivos de prueba', 'capturas': 'Capturas e informes'}
TEST_DOWNLOADS_MB = (1, 10, 100)


def _link(label: str, href: str) -> str:
    return f'<a class="panel resource" href="{href}">{label}<span class="arrow" aria-hidden="true">›</span></a>'


def _card(title: str, detail: str) -> str:
    return f'<span><strong>{title}</strong><small>{detail}</small></span>'


def folder_title(parts: list[str]) -> str:
    if len(parts) == 1:
        return SECTION_LABELS.get(parts[0], parts[0])
    return parts[-1] if parts else 'Archivos'


def breadcrumbs(parts: list[str]) -> tuple[str, str]:
    """Migas de pan en HTML y la ruta de la carpeta superior."""
    crumbs = ['<a href="/">Inicio</a>']
    for index, part in enumerate(parts):
        label = SECTION_LABELS.get(part, part) if index == 0 else part
        href = '/' + '/'.join(quote(piece, safe='') for piece in parts[:index + 1]) + '/'
        crumbs.append(f'<span aria-hidden="true">/</span><a href="{href}">{html.escape(label)}</a>')
    parent = '/' + '/'.join(quote(piece, safe='') for piece in parts[:-1])
    return ''.join(crumbs), parent if parent == '/' else parent + '/'


def file_row(name: str, is_folder: bool, size: int | None) -> str:
    """Una fila del explorador. `size` es None si no se pudo leer."""
    href = quote(name, safe='') + ('/' if is_folder else '')
    if is_folder:
        detail, icon = 'Carpeta · Abrir', FOLDER_ICON
    else:
        detail = 'Archivo · Descargar' if size is None else f'{size:,} bytes · Descargar'.replace(',', '.')
        icon = FILE_ICON
    download = '' if is_folder else ' download'
    return (
        f'<li><a class="resource" href="{href}"{download}>'
        f'<span class="mark" aria-hidden="true"><svg viewBox="0 0 24 24">{icon}</svg></span>'
        f'<span class="file-name"><strong>{html.escape(name)}</strong><small>{detail}</small></span>'
        '<span class="arrow" aria-hidden="true">›</span></a></li>')


def directory_content(parts: list[str], entries: list[tuple[str, bool, int | None]]) -> str:
    """Contenido de la pagina de una carpeta. `entries` son (nombre, es_carpeta, bytes)."""
    crumbs, parent = breadcrumbs(parts)
    rows = [file_row(name, is_folder, size) for name, is_folder, size in entries]
    listing = ('<ul class="panel file-list">' + ''.join(rows) + '</ul>' if rows else
               '<div class="panel empty">Esta carpeta está vacía.</div>')
    return (
        '<nav class="breadcrumbs" aria-label="Ruta de navegación">' + crumbs + '</nav>'
        f'<p class="eyebrow">Recursos compartidos</p><h1>{html.escape(folder_title(parts))}</h1>'
        f'<p class="intro">{len(entries)} elementos · Explorá las carpetas o descargá un archivo.</p>'
        + listing + f'<a class="back-link" href="{parent}">← Volver al nivel anterior</a>')


def shared_resources(has_captures: bool, remote_control: bool) -> str:
    """Tarjetas opcionales de la portada: capturas, registros y control remoto."""
    cards = ''
    if has_captures:
        cards += (
            '<a class="panel resource" href="/capturas/">'
            '<span class="mark" aria-hidden="true"><svg viewBox="0 0 24 24">'
            '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/>'
            '<path d="M14 3v6h6M8 13h8M8 17h5"/></svg></span>'
            '<span><strong>Capturas e informes</strong>'
            '<small>Consultá los resultados de Mulita.</small></span>'
            '<span class="arrow" aria-hidden="true">›</span></a>')
        cards += _link(_card('Registro de actividades', 'Consultar jornadas y exportar registros.'), '/actividad/')
        cards += _link(_card('Bitácora técnica', 'Acciones, resultados y archivos exportados por jornada.'), '/bitacora/')
    if remote_control:
        cards += _link('<strong>Control remoto</strong>', '/control')
    return cards


def download_links() -> str:
    return ''.join(
        f'<a class="download" href="/prueba/{mb}" download="mulita-prueba-{mb}MB.bin">'
        f'<span><strong>{mb} MB</strong><small>Descargar archivo</small></span>'
        '<svg aria-hidden="true" viewBox="0 0 24 24">'
        '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></svg></a>'
        for mb in TEST_DOWNLOADS_MB)


def home_content(scheme: str, client: str, server: str, timestamp: str,
                 has_captures: bool, remote_control: bool) -> str:
    return Template(HOME).substitute(
        scheme=scheme, client=html.escape(client), server=html.escape(server), timestamp=timestamp,
        captures=shared_resources(has_captures, remote_control), downloads=download_links())
