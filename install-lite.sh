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
  libinput10
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

install_dht() {
  # Pi OS de 64 bits no trae "Hardware : BCM..." en /proc/cpuinfo.
  # Adafruit_DHT 1.4.0 aborta la compilacion. Se fuerza el driver de Pi 2/3/4.
  local src py status
  py="$ROOT/.venv/bin/python"
  src="$(mktemp -d)"
  status=0
  "$py" -m pip install setuptools wheel || status=1
  if [[ "$status" -eq 0 ]]; then
    "$py" -m pip download 'Adafruit_DHT==1.4.0' --no-binary :all: -d "$src" || status=1
  fi
  if [[ "$status" -eq 0 ]]; then
    tar -xzf "$src"/Adafruit_DHT-1.4.0.tar.gz -C "$src" || status=1
  fi
  if [[ "$status" -eq 0 ]]; then
    "$py" - "$src/Adafruit_DHT-1.4.0/Adafruit_DHT/platform_detect.py" <<'PY' || status=1
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text()
needle = "def pi_version():"
if needle not in text:
    raise SystemExit("platform_detect.py no tiene pi_version")
path.write_text(text.replace(needle, "def pi_version():\n    return 3\n", 1))
PY
  fi
  if [[ "$status" -eq 0 ]]; then
    "$py" -m pip install --no-build-isolation "$src/Adafruit_DHT-1.4.0" || status=1
  fi
  rm -rf "$src"
  return "$status"
}

echo "Instalando dependencias Python..."
.venv/bin/python -m pip install --upgrade pip
grep -v '^Adafruit_DHT' requirements.txt | .venv/bin/python -m pip install -r /dev/stdin
if ! install_dht; then
  echo "Aviso: no se instalo Adafruit_DHT. La app arranca igual; el DHT11 no va a leer."
fi
if [[ -r /proc/device-tree/model ]] && tr -d '\0' < /proc/device-tree/model | grep -q "Pi 5"; then
  echo "Aviso: esta libreria no lee el GPIO de la Raspberry Pi 5."
fi

# El ft5x06 se anuncia como mouse. Qt entonces lee mal el arrastre y el dedo salta.
touch_rule="/etc/udev/rules.d/99-mulita-touch.rules"
if [[ ! -f "$touch_rule" ]] || ! grep -q ft5x06 "$touch_rule"; then
  echo "Marcando el panel ft5x06 como pantalla tactil..."
  as_root tee "$touch_rule" >/dev/null <<'EOF'
ACTION=="add|change", SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="*ft5x06*", ENV{ID_INPUT}="1", ENV{ID_INPUT_TOUCHSCREEN}="1", ENV{ID_INPUT_MOUSE}="0"
EOF
  as_root udevadm control --reload-rules || true
  as_root udevadm trigger --subsystem-match=input || true
fi

echo "Activando el arranque al boot..."
unit="$(mktemp)"
cat > "$unit" <<EOF
[Unit]
Description=Mulita Network Tool
After=multi-user.target
Conflicts=getty@tty1.service

[Service]
Type=simple
WorkingDirectory=$ROOT
Environment=QT_QPA_PLATFORM=eglfs
Environment=QT_QPA_EGLFS_INTEGRATION=eglfs_kms
Environment=QT_QPA_EGLFS_HIDECURSOR=1
ExecStart=$ROOT/.venv/bin/python main.py
Restart=on-failure
RestartSec=3
StandardInput=tty
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
KillSignal=SIGTERM
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
EOF
as_root cp "$unit" /etc/systemd/system/mulita.service
rm -f "$unit"
as_root systemctl daemon-reload
as_root systemctl enable mulita.service

echo "Listo. Al reiniciar, Mulita se abre sola en la pantalla."
echo "Probar ahora: sudo systemctl start mulita"
echo "Ver el registro: journalctl -u mulita -f"
