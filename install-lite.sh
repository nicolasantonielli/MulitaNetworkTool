#!/bin/sh
# Instala lo necesario para Mulita en Raspberry Pi OS Lite, sin escritorio.
#
# Uso, en el equipo:
#   bash install-lite.sh
#   bash run.sh

if [ -z "${BASH_VERSION-}" ]; then
  exec bash "$0" "$@"
fi
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Este script es para Raspberry Pi OS Lite."
  exit 1
fi

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

APT_PACKAGES=(
  python3
  python3-venv
  python3-pip
  python3-dev
  build-essential
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
  libqt5gui5
  libegl1
  libgles2
  libgbm1
  libdrm2
  fonts-dejavu-core
  iproute2
  tcpdump
  mtr-tiny
  iputils-ping
  nmap
  netdiscover
  wakeonlan
  curl
  ca-certificates
  speedtest-cli
  git
  psmisc
)

if ! dpkg -s "${APT_PACKAGES[@]}" >/dev/null 2>&1; then
  echo "Instalando paquetes del sistema..."
  export DEBIAN_FRONTEND=noninteractive
  as_root apt-get update
  as_root apt-get install -y "${APT_PACKAGES[@]}"
fi

if [[ ! -x /usr/bin/speedtest && -x /usr/bin/speedtest-cli ]]; then
  as_root ln -sfn /usr/bin/speedtest-cli /usr/bin/speedtest
fi

ensure_path() {
  local expected="$1"
  local name found
  if [[ -x "$expected" ]]; then
    return 0
  fi
  name="$(basename "$expected")"
  found="$(command -v "$name" || true)"
  if [[ -n "$found" ]]; then
    as_root ln -sfn "$found" "$expected"
    echo "Enlace $expected -> $found"
    return 0
  fi
  echo "Falta el comando $expected" >&2
  return 1
}

missing=0
for path in \
  /bin/tcpdump /bin/mtr /bin/ping /bin/nmap /sbin/netdiscover \
  /bin/wakeonlan /bin/speedtest /bin/curl /usr/bin/ip /usr/bin/git /bin/bash
do
  ensure_path "$path" || missing=1
done
command -v killall >/dev/null 2>&1 || { echo "Falta el comando killall" >&2; missing=1; }
command -v poweroff >/dev/null 2>&1 || { echo "Falta el comando poweroff" >&2; missing=1; }
if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

target_user="${SUDO_USER:-$USER}"
if [[ -n "$target_user" && "$target_user" != "root" ]]; then
  as_root usermod -aG video,render "$target_user"
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "Creando entorno virtual..."
  python3 -m venv --system-site-packages .venv
fi

echo "Instalando dependencias Python..."
.venv/bin/python -m pip install --upgrade pip
grep -v '^Adafruit_DHT' requirements.txt | .venv/bin/python -m pip install -r /dev/stdin
if ! .venv/bin/python -m pip install 'Adafruit_DHT'; then
  echo "Aviso: no se instalo Adafruit_DHT. La app arranca igual; el DHT11 no va a leer."
fi

echo "Listo. Arranque con: bash run.sh"
