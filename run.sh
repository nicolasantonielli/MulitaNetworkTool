#!/bin/sh
# Arranca Mulita en un entorno virtual.
#
# En Raspberry Pi OS Lite, install-lite.sh instala Qt, el teclado virtual
# y las herramientas de red. PyQt5 entra por apt; el entorno virtual lo ve
# con --system-site-packages.
#
# Uso, en el equipo:
#   bash install-lite.sh
#   bash run.sh
#   bash run.sh --tk

# sh en Debian es dash y rechaza "pipefail". El resto del script es bash.
if [ -z "${BASH_VERSION-}" ]; then
  exec bash "$0" "$@"
fi
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

bash "$ROOT/install-lite.sh"

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  if [[ -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=:0
  else
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-eglfs}"
    export QT_QPA_EGLFS_HIDECURSOR=1
  fi
fi

exec .venv/bin/python main.py "$@"
