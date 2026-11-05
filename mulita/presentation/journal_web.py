"""Escaped HTML timeline using the device palette and journal vocabulary."""
from html import escape

from mulita.presentation.i18n import Translator
from mulita.presentation.theme import palette_for


def timeline(entries, settings):
    tr = Translator(settings.language.value).tr
    colors = palette_for(settings.theme)
    variables = {'bg': colors.background, 'surface': colors.surface, 'alt': colors.surface_alt,
                 'high': colors.surface_high, 'border': colors.border, 'text': colors.text,
                 'muted': colors.text_muted, 'primary': colors.primary, 'success': colors.success}
    palette = ';'.join(f'--{key}:{value}!important' for key, value in variables.items())
    style = '''
    #theme {display:none!important}
    .timeline {list-style:none;padding:0;margin:24px 0}
    .timeline li {display:grid;grid-template-columns:100px minmax(0,1fr);gap:28px;position:relative;padding-bottom:22px}
    .timeline li:before {content:'';position:absolute;left:112px;top:8px;bottom:-8px;width:1px;background:var(--border)}
    .timeline li:after {content:'';position:absolute;left:105px;top:8px;width:10px;height:10px;border:3px solid var(--accent);border-radius:50%;background:var(--bg)}
    .timeline time {padding-top:2px;font-size:18px;font-weight:600}
    .timeline time small {display:block;font-size:12px;color:var(--muted);font-weight:400}
    .timeline article {padding:20px;min-width:0}
    .timeline .kind {display:inline-block;border:1px solid var(--accent);border-radius:7px;padding:4px 12px;background:var(--high);font-weight:600;overflow-wrap:anywhere}
    .timeline p {white-space:pre-wrap;overflow-wrap:anywhere;margin:14px 0 0}
    .timeline h2 {margin-top:18px;color:var(--muted);font-size:13px}
    @media(max-width:480px){.timeline li{grid-template-columns:76px minmax(0,1fr);gap:20px}.timeline li:before{left:84px}.timeline li:after{left:77px}.timeline article{padding:12px}.timeline time{font-size:15px}}
    '''
    rows = []
    for entry in entries:
        accent = {'failed': colors.danger, 'completed': colors.success, 'stop': colors.warning}.get(entry['phase'], colors.primary)
        result = (f'<h2>{escape(tr("journalResults"))}</h2><p>{escape(entry["results"])}</p>'
                  if entry['results'] else '')
        rows.append(f'<li style="--accent:{accent}"><time datetime="{escape(entry["timestamp"], quote=True)}">'
                    f'{escape(entry["time"])}<small>{escape(entry["date"])}</small></time>'
                    f'<article class="panel"><span class="kind">{escape(entry["kind"] or tr("journalLegacy"))}</span>'
                    f'<p>{escape(entry["text"])}</p>{result}</article></li>')
    return f'<style>:root{{{palette}}}{style}</style><ol class="timeline">' + ''.join(rows) + '</ol>'
