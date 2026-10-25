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

boot_dir() {
  if [[ -d /boot/firmware ]]; then
    echo /boot/firmware
  else
    echo /boot
  fi
}

# La consola de texto en tty1 tapa la interfaz. El kernel habla por el serial
# y la pantalla queda libre para la aplicacion.
configure_cmdline() {
  local file="$1" line word
  local -a words=() new=()
  local seen_quiet=0 seen_log=0 seen_logo=0 seen_cursor=0 seen_blank=0 seen_status=0 seen_tty3=0
  line="$(tr -s '[:space:]' ' ' < "$file")"
  read -r -a words <<< "$line"
  for word in "${words[@]}"; do
    case "$word" in
      console=tty1|splash) continue ;;
      console=tty3) seen_tty3=1 ;;
      quiet) seen_quiet=1 ;;
      loglevel=*) seen_log=1; word="loglevel=3" ;;
      logo.nologo) seen_logo=1 ;;
      vt.global_cursor_default=*) seen_cursor=1; word="vt.global_cursor_default=0" ;;
      consoleblank=*) seen_blank=1; word="consoleblank=0" ;;
      systemd.show_status=*) seen_status=1; word="systemd.show_status=false" ;;
    esac
    new+=("$word")
  done
  [[ "$seen_quiet" -eq 1 ]] || new+=(quiet)
  [[ "$seen_log" -eq 1 ]] || new+=(loglevel=3)
  [[ "$seen_logo" -eq 1 ]] || new+=(logo.nologo)
  [[ "$seen_cursor" -eq 1 ]] || new+=(vt.global_cursor_default=0)
  [[ "$seen_blank" -eq 1 ]] || new+=(consoleblank=0)
  [[ "$seen_status" -eq 1 ]] || new+=(systemd.show_status=false)
  # tty3 queda como consola de rescate (Ctrl+Alt+F3). tty1 es la aplicacion.
  [[ "$seen_tty3" -eq 1 ]] || new+=(console=tty3)
  local rebuilt="${new[*]}"
  if [[ "$rebuilt" != *root=* || "$rebuilt" != *rootwait* ]]; then
    echo "No se modifico $file: sin esa linea la Raspberry no arranca."
    return 0
  fi
  if [[ ! -f "$file.mulita-bak" ]]; then
    as_root cp -a "$file" "$file.mulita-bak"
  fi
  printf '%s\n' "$rebuilt" | as_root tee "$file" >/dev/null
}

configure_boot() {
  local dir file
  dir="$(boot_dir)"
  file="$dir/cmdline.txt"
  if [[ -f "$file" ]]; then
    echo "Dejando la pantalla para la aplicacion..."
    configure_cmdline "$file"
  else
    echo "Aviso: no esta $file. No se cambio la consola del kernel."
  fi
  file="$dir/config.txt"
  if [[ -f "$file" ]] && ! grep -q 'mulita-kiosk' "$file"; then
    as_root tee -a "$file" >/dev/null <<'EOF'

# mulita-kiosk
disable_splash=1
EOF
  fi
}

configure_boot

echo "Activando el arranque al boot..."
unit="$(mktemp)"
cat > "$unit" <<EOF
[Unit]
Description=Mulita Network Tool
After=systemd-user-sessions.service systemd-udev-trigger.service
Conflicts=getty@tty1.service
Before=getty@tty1.service

[Service]
Type=simple
WorkingDirectory=$ROOT
Environment=QT_QPA_PLATFORM=eglfs
Environment=QT_QPA_EGLFS_INTEGRATION=eglfs_kms
ExecStart=$ROOT/.venv/bin/python main.py
Restart=always
RestartSec=3
StandardInput=tty
StandardOutput=journal
StandardError=journal
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
TTYVTDisallocate=yes
KillSignal=SIGTERM
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
EOF
as_root cp "$unit" /etc/systemd/system/mulita.service
rm -f "$unit"
as_root systemctl daemon-reload
# tty1 lo usa la aplicacion. No se enmascara getty: tty3 sigue permitiendo entrar
# con teclado si la aplicacion no abre. Enmascararlo deja la pantalla negra y sin login.
as_root systemctl unmask getty@tty1.service || true
as_root systemctl disable getty@tty1.service || true
as_root systemctl enable getty@tty3.service || true
as_root systemctl enable mulita.service

echo "Listo. Al reiniciar, Mulita se abre sola en la pantalla."
echo "Aplicar ahora: sudo reboot"
echo "Ver el registro: journalctl -u mulita -f"
