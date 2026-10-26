"""Configura el arranque probado con la BTT-PITFT50 V1.0 en Raspberry Pi 4."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile


BEGIN = '# mulita-btt-pitft50-v1 begin'
END = '# mulita-btt-pitft50-v1 end'
SETTINGS = (
    '[all]',
    'display_auto_detect=0',
    'dtoverlay=vc4-kms-dsi-7inch,disable_touch',
    'dtoverlay=rpi-ft5406',
    'disable_touchscreen=0',
    'disable_splash=1',
)


def configure_text(text: str) -> str:
    lines = []
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == BEGIN:
            if in_block:
                raise ValueError('Bloque tactil de Mulita anidado')
            in_block = True
            continue
        if stripped == END:
            if not in_block:
                raise ValueError('Fin de bloque tactil de Mulita sin inicio')
            in_block = False
            continue
        if in_block:
            continue
        if stripped == '# mulita-kiosk':
            continue
        key, separator, value = stripped.partition('=')
        key = key.strip()
        value = value.split('#', 1)[0].strip()
        replaced = key in ('display_auto_detect', 'disable_touchscreen', 'disable_splash')
        replaced |= key == 'dtoverlay' and value.split(',', 1)[0].strip() in (
            'vc4-kms-dsi-7inch', 'rpi-ft5406')
        if separator and replaced:
            lines.append('# mulita reemplaza: ' + stripped)
        else:
            lines.append(line)
    if in_block:
        raise ValueError('Bloque tactil de Mulita sin cierre; no se modifico config.txt')
    return '\n'.join(lines).rstrip() + '\n\n' + '\n'.join((BEGIN, *SETTINGS, END)) + '\n'


def configure_file(path: Path) -> bool:
    original = path.read_text(encoding='utf-8')
    updated = configure_text(original)
    if updated == original:
        return False
    backup = path.with_name(path.name + '.mulita-bak')
    if not backup.exists():
        shutil.copy2(path, backup)
    descriptor, name = tempfile.mkstemp(prefix='.mulita-config-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        shutil.copymode(path, temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


if __name__ == '__main__':
    changed = configure_file(Path(sys.argv[1]))
    if changed:
        print('BTT-PITFT50 V1.0: tactil por firmware configurado. Reiniciar para aplicarlo.')
    else:
        print('BTT-PITFT50 V1.0: la configuracion del tactil ya esta aplicada.')
