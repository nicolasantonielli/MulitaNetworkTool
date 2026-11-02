#!/bin/sh
# Instala Mulita en Raspberry Pi OS Lite para un panel DSI de 5 o 7 pulgadas.
#
# Uso:
#   bash install-lite.sh 5
#   bash install-lite.sh 7
#   sudo reboot
# Inicio manual posterior a la instalación: bash run.sh
# Opciones: --capture-dir /ruta/capturas --state-dir /ruta/privada
# El servicio se habilita al finalizar; la aplicación inicia después del reinicio.

if [ -z "${BASH_VERSION-}" ]; then
  exec bash "$0" "$@"
fi
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Error: este instalador requiere Raspberry Pi OS Lite con systemd." >&2
  exit 1
fi

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

# Validar los argumentos antes de instalar paquetes o modificar archivos del sistema.
usage() {
  echo "Uso: bash install-lite.sh <5|7> [--capture-dir /ruta/absoluta] [--state-dir /ruta/absoluta]"
  echo "Paneles: 5 = BTT-PITFT50 V1.0; 7 = Waveshare 7_0_inchH en DSI1."
}
SCREEN=""
INSTALL_OPTIONS=()
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    5|7)
      if [[ -n "$SCREEN" ]]; then
        echo "Error: la pantalla debe especificarse una sola vez." >&2
        exit 1
      fi
      SCREEN="$1"
      shift ;;
    --capture-dir|--state-dir)
      if [[ "$#" -lt 2 || "$2" != /* ]]; then
        echo "Error: $1 requiere una ruta absoluta." >&2
        exit 1
      fi
      INSTALL_OPTIONS+=("$1" "$2")
      shift 2 ;;
    *) echo "Error: opción no reconocida: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$SCREEN" ]]; then
  echo "Error: se debe seleccionar una pantalla de 5 o 7 pulgadas." >&2
  usage
  exit 1
fi

# Seleccionar únicamente los overlays y el configurador del panel solicitado.
select_display() {
  case "$SCREEN" in
    5)
      DISPLAY_NAME="BTT-PITFT50 V1.0 de 5 pulgadas"
      DISPLAY_HELPER="scripts/configure_display.py"
      DISPLAY_OVERLAYS=(vc4-kms-v3d vc4-kms-dsi-7inch rpi-ft5406) ;;
    7)
      DISPLAY_NAME="Waveshare 7_0_inchH de 7 pulgadas (DSI1)"
      DISPLAY_HELPER="scripts/configure_display_7.py"
      DISPLAY_OVERLAYS=(vc4-kms-v3d vc4-kms-dsi-waveshare-panel) ;;
    *) echo "Error: la pantalla seleccionada no es válida." >&2; return 1 ;;
  esac
}
select_display

for command in apt-get dpkg-query systemctl systemd-analyze; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Error: no se encuentra el comando requerido: $command." >&2
    exit 1
  fi
done
for file in requirements.txt main.py scripts/configure_installation.py scripts/configure_display_7.py scripts/configure_display.py scripts/verify_qt_runtime.py; do
  if [[ ! -f "$ROOT/$file" ]]; then
    echo "Error: falta un archivo requerido del repositorio: $file." >&2
    exit 1
  fi
done

# Qt/QML, herramientas de diagnóstico, administración de red y servicios de prueba.
# El teclado integrado se implementa en QML y no utiliza Qt Virtual Keyboard.
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
  libqt5svg5
  libqt5gui5
  libegl1
  libgles2
  libgbm1
  libdrm2
  fonts-dejavu-core
  libinput10
  iproute2
  network-manager
  util-linux
  passwd
  tar
  iw
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
  iperf3
  dnsmasq-base
  openssh-server
  openssl
)

# Un paquete con archivos de configuración residuales no se considera instalado.
packages_ready() {
  local package status
  for package in "$@"; do
    status="$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null)" || return 1
    [[ "$status" == "install ok installed" ]] || return 1
  done
}

if ! packages_ready "${APT_PACKAGES[@]}"; then
  echo "Instalando paquetes del sistema..."
  as_root apt-get update
  as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y "${APT_PACKAGES[@]}"
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
    echo "Enlace de ejecutable configurado: $expected -> $found."
    return 0
  fi
  echo "Error: no se encuentra el ejecutable requerido: $expected." >&2
  return 1
}

# testssl.sh es una dependencia opcional para el análisis TLS. Su ausencia
# no impide instalar las demás funciones de la aplicación.
if ! command -v testssl >/dev/null 2>&1 && ! command -v testssl.sh >/dev/null 2>&1; then
  echo "Instalando testssl.sh..."
  as_root apt-get update || true
  as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y testssl.sh \
    || echo "Advertencia: testssl.sh no está disponible; el análisis de certificados TLS permanecerá deshabilitado."
fi
# Normalizar la ubicación del ejecutable TLS cuando se distribuye como testssl.sh.
if [[ ! -x /usr/bin/testssl ]]; then
  found="$(command -v testssl.sh || command -v testssl || true)"
  if [[ -n "$found" ]]; then
    as_root ln -sfn "$found" /usr/bin/testssl
    echo "Enlace de ejecutable configurado: /usr/bin/testssl -> $found."
  fi
fi

missing=0
for path in \
  /bin/tcpdump /bin/mtr /bin/ping /bin/nmap /sbin/netdiscover /usr/sbin/iw \
  /usr/bin/nmcli /usr/bin/systemctl /usr/bin/systemd-run /usr/sbin/runuser \
  /bin/wakeonlan /bin/speedtest /bin/curl /usr/bin/ip /usr/sbin/tc /usr/bin/mount /usr/bin/lsblk /usr/bin/git /bin/bash \
  /usr/bin/iperf3 /usr/sbin/dnsmasq /usr/sbin/sshd /usr/bin/ssh-keygen /usr/bin/openssl \
  /usr/sbin/useradd /usr/sbin/userdel /usr/sbin/chpasswd /usr/bin/getent /usr/bin/chown
do
  ensure_path "$path" || missing=1
done
command -v killall >/dev/null 2>&1 || { echo "Error: no se encuentra el comando killall." >&2; missing=1; }
command -v poweroff >/dev/null 2>&1 || { echo "Error: no se encuentra el comando poweroff." >&2; missing=1; }
if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

target_user="${SUDO_USER:-$(id -un)}"
if [[ -n "$target_user" && "$target_user" != "root" ]]; then
  as_root usermod -aG video,render "$target_user"
fi

# Python 3.10 o posterior es necesario para las anotaciones y API del proyecto.
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Error: se requiere Python 3.10 o posterior.")'

# NetworkManager es el backend utilizado para Ethernet, VLAN y Wi-Fi.
as_root systemctl enable NetworkManager.service
if ! as_root systemctl is-active --quiet NetworkManager.service; then
  as_root systemctl start NetworkManager.service
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "Creando entorno virtual..."
  python3 -m venv --system-site-packages .venv
fi

install_dht() {
  # Adafruit_DHT 1.4.0 no reconoce correctamente algunos sistemas de 64 bits.
  # Seleccionar el controlador compatible con Raspberry Pi 2, 3 y 4.
  local src py status
  py="$ROOT/.venv/bin/python"
  src="$(mktemp -d)" || return 1
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
    raise SystemExit("Error: platform_detect.py no contiene la función pi_version.")
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
.venv/bin/python -m pip check
# El controlador DHT heredado no es compatible con Raspberry Pi 5.
if [[ -r /proc/device-tree/model ]] && tr -d '\0' < /proc/device-tree/model | grep -q "Pi 5"; then
  echo "Advertencia: el controlador DHT11 no es compatible con Raspberry Pi 5; se omite su instalación."
elif .venv/bin/python -c 'import Adafruit_DHT' >/dev/null 2>&1; then
  echo "El controlador DHT11 ya está instalado."
elif ! install_dht; then
  echo "Advertencia: no se pudo instalar Adafruit_DHT; la aplicación funcionará sin lecturas DHT11."
fi

# Verificar los módulos Python y QML antes de modificar la configuración de arranque.
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python "$ROOT/scripts/verify_qt_runtime.py"

# Seleccionar la partición de arranque utilizada por Raspberry Pi OS.

boot_dir() {
  if [[ -d /boot/firmware ]]; then
    echo /boot/firmware
  else
    echo /boot
  fi
}

# Reservar tty1 para la aplicación y conservar tty3 como consola de recuperación.
# Mantener los parámetros de raíz y cualquier consola serie existente.
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
  # Habilitar la consola de recuperación tty3 (Ctrl+Alt+F3).
  [[ "$seen_tty3" -eq 1 ]] || new+=(console=tty3)
  local rebuilt="${new[*]}"
  if [[ "$rebuilt" != *root=* || "$rebuilt" != *rootwait* ]]; then
    echo "Error: $file no contiene root= y rootwait; se cancela la modificación para preservar el arranque." >&2
    return 1
  fi
  if [[ ! -f "$file.mulita-bak" ]]; then
    as_root cp -a "$file" "$file.mulita-bak"
  fi
  printf '%s\n' "$rebuilt" | as_root tee "$file" >/dev/null
}

configure_boot() {
  local dir file
  dir="$(boot_dir)"
  file="$dir/config.txt"
  if [[ ! -f "$file" ]]; then
    echo "Error: no existe $file; no se puede configurar el panel $DISPLAY_NAME." >&2
    return 1
  fi
  local overlay
  for overlay in "${DISPLAY_OVERLAYS[@]}"; do
    if [[ ! -f "$dir/overlays/$overlay.dtbo" ]]; then
      echo "Error: falta $dir/overlays/$overlay.dtbo; se requiere un kernel con soporte para este panel. No se modificó la configuración de arranque." >&2
      return 1
    fi
  done
  echo "Configurando el panel $DISPLAY_NAME..."
  as_root python3 "$ROOT/$DISPLAY_HELPER" "$file"
  file="$dir/cmdline.txt"
  if [[ -f "$file" ]]; then
    echo "Configurando la consola para el inicio de la aplicación..."
    configure_cmdline "$file"
  else
    echo "Advertencia: no existe $file; se conserva la configuración de consola actual."
  fi
}

echo "Configurando las rutas de instalación y el servicio systemd..."
as_root python3 "$ROOT/scripts/configure_installation.py" \
  --repository "$ROOT" --user "$target_user" "${INSTALL_OPTIONS[@]}"
as_root systemd-analyze verify /etc/systemd/system/mulita.service

# Aplicar la configuración del panel después de verificar la unidad de servicio.
configure_boot
as_root systemctl daemon-reload
# Deshabilitar el inicio de sesión en tty1 sin enmascarar las consolas.
# Mantener tty3 disponible para diagnóstico y recuperación.
as_root systemctl unmask getty@tty1.service || true
as_root systemctl disable getty@tty1.service || true
as_root systemctl enable getty@tty3.service || true
as_root systemctl enable mulita.service

echo "Instalación finalizada. Mulita iniciará automáticamente después del reinicio."
echo "Para aplicar la configuración de pantalla: sudo reboot"
echo "Consulta del registro: sudo journalctl -u mulita -f"
