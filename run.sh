#!/bin/sh
# Arranca Mulita en un entorno virtual.
#
# En Raspberry Pi OS Lite, install-lite.sh instala Qt y las herramientas de red.
# PyQt5 se instala mediante APT y se utiliza desde el entorno virtual con
# --system-site-packages. El teclado integrado se implementa en QML.
#
# Uso, en el equipo:
#   bash install-lite.sh 5  # o 7, según el panel instalado
#   bash run.sh
#   bash run.sh --tk

# sh en Debian es dash y rechaza "pipefail". El resto del script es bash.
if [ -z "${BASH_VERSION-}" ]; then
  exec bash "$0" "$@"
fi
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Falta el entorno virtual. Ejecute bash install-lite.sh 5 o bash install-lite.sh 7 antes de iniciar Mulita." >&2
  exit 1
fi

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  if [[ -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=:0
  else
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-eglfs}"
  fi
fi

exec .venv/bin/python main.py "$@"
