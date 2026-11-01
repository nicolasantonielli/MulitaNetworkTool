"""Configura el panel Waveshare 7_0_inchH en DSI1 y conserva un respaldo del arranque."""
from pathlib import Path
import sys

if __package__:
    from .configure_display import configure_file
else:
    from configure_display import configure_file

BEGIN = '# mulita-waveshare-7 begin'
END = '# mulita-waveshare-7 end'
SETTINGS = (
    '[all]',
    'display_auto_detect=0',
    'dtoverlay=vc4-kms-v3d',
    '# Conexión activa: DSI1.',
    'dtoverlay=vc4-kms-dsi-waveshare-panel,7_0_inchH',
    '# Configuración alternativa para conexión DSI0 (deshabilitada).',
    '#dtoverlay=vc4-kms-dsi-waveshare-panel,7_0_inchH,dsi0',
    'disable_touchscreen=0',
    'disable_splash=1',
)


def configure_text(text: str) -> str:
    lines = []
    block_end = None
    blocks = {BEGIN: END, '# mulita-btt-pitft50-v1 begin': '# mulita-btt-pitft50-v1 end'}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in blocks:
            if block_end:
                raise ValueError('Error: se detectó un bloque de configuración de pantalla anidado.')
            block_end = blocks[stripped]
            continue
        if stripped in blocks.values():
            if stripped != block_end:
                raise ValueError('Error: se detectó un cierre de bloque de pantalla inesperado.')
            block_end = None
            continue
        if block_end or stripped == '# mulita-kiosk':
            continue
        key, separator, value = stripped.partition('=')
        key = key.strip()
        value = value.split('#', 1)[0].strip()
        replaced = key in ('display_auto_detect', 'disable_touchscreen', 'disable_splash')
        replaced |= key == 'dtoverlay' and value.split(',', 1)[0].strip() in (
            'vc4-kms-v3d', 'vc4-fkms-v3d', 'vc4-kms-dsi-7inch',
            'rpi-ft5406', 'vc4-kms-dsi-waveshare-panel')
        lines.append('# mulita reemplaza: ' + stripped if separator and replaced else line)
    if block_end:
        raise ValueError('Error: el bloque de pantalla está incompleto; config.txt no fue modificado.')
    return '\n'.join(lines).rstrip() + '\n\n' + '\n'.join((BEGIN, *SETTINGS, END)) + '\n'


if __name__ == '__main__':
    changed = configure_file(Path(sys.argv[1]), configure_text)
    print('Waveshare 7 pulgadas DSI1: ' + (
        'configuración aplicada. Se requiere reiniciar el equipo.' if changed else 'la configuración ya se encuentra aplicada.'))
