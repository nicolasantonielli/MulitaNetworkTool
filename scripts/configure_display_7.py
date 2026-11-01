"""Configura Waveshare 7_0_inchH en DSI1 con los overlays probados en el equipo."""
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
    '# DSI1 Use',
    'dtoverlay=vc4-kms-dsi-waveshare-panel,7_0_inchH',
    '# DSI0 Use',
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
                raise ValueError('Bloque de pantalla anidado')
            block_end = blocks[stripped]
            continue
        if stripped in blocks.values():
            if stripped != block_end:
                raise ValueError('Fin de bloque de pantalla inesperado')
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
        raise ValueError('Bloque de pantalla sin cierre; no se modifico config.txt')
    return '\n'.join(lines).rstrip() + '\n\n' + '\n'.join((BEGIN, *SETTINGS, END)) + '\n'


if __name__ == '__main__':
    changed = configure_file(Path(sys.argv[1]), configure_text)
    print('Waveshare 7 pulgadas DSI1: ' + (
        'configurada. Reiniciar para aplicarlo.' if changed else 'ya configurada.'))
