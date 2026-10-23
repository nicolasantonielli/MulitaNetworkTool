#!/usr/bin/env bash
# Arranca Mulita en un entorno virtual.
#
# PyQt5 no tiene paquetes pip para la Raspberry Pi. Se instala por apt y el
# entorno lo ve porque se crea con --system-site-packages. El resto
# (Pillow, ttkbootstrap, Adafruit_DHT) se instala con pip dentro de .venv.
#
# Uso, en el equipo:
#   bash run.sh
#   bash run.sh --tk
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

APT_PACKAGES=(
  python3
  python3-venv
  python3-pip
  python3-pyqt5
  python3-pyqt5.qtquick
  python3-pyqt5.qtsvg
  qml-module-qtquick2
  qml-module-qtquick-controls2
  qml-module-qtquick-layouts
  qml-module-qtquick-window2
  qml-module-qtquick-virtualkeyboard
  qtvirtualkeyboard-plugin
  libqt5svg5
)

if ! dpkg -s "${APT_PACKAGES[@]}" >/dev/null 2>&1; then
  echo "Instalando PyQt5 y los modulos QML del sistema..."
  sudo apt-get update
  sudo apt-get install -y "${APT_PACKAGES[@]}"
fi

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv --system-site-packages .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  if [[ -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=:0
  else
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-eglfs}"
  fi
fi

exec .venv/bin/python main.py "$@"
