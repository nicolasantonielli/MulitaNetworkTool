from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Modo test en aplicacion
# Desactiva Sensor de temperatura
# Desactiva Fullscreen
TEST = False


@dataclass(frozen=True)
class Binaries:
    tcpdump: str = '/bin/tcpdump'
    mtr: str = '/bin/mtr'
    ping: str = '/bin/ping'
    nmap: str = '/bin/nmap'
    netdiscover: str = '/sbin/netdiscover'
    wakeonlan: str = '/bin/wakeonlan'
    speedtest: str = '/bin/speedtest'
    curl: str = '/bin/curl'
    ip: str = '/usr/bin/ip'
    tc: str = '/usr/sbin/tc'
    mount: str = '/usr/bin/mount'
    lsblk: str = '/usr/bin/lsblk'
    git: str = '/usr/bin/git'
    bash: str = '/bin/bash'
    nmcli: str = '/usr/bin/nmcli'
    iw: str = '/usr/sbin/iw'
    systemctl: str = '/usr/bin/systemctl'
    systemd_run: str = '/usr/bin/systemd-run'
    iperf3: str = '/usr/bin/iperf3'
    dnsmasq: str = '/usr/sbin/dnsmasq'
    sshd: str = '/usr/sbin/sshd'
    ssh_keygen: str = '/usr/bin/ssh-keygen'
    openssl: str = '/usr/bin/openssl'
    testssl: str = '/usr/bin/testssl'
    getent: str = '/usr/bin/getent'
    useradd: str = '/usr/sbin/useradd'
    userdel: str = '/usr/sbin/userdel'
    chpasswd: str = '/usr/sbin/chpasswd'
    chown: str = '/usr/bin/chown'
    runuser: str = '/usr/sbin/runuser'
    python: str = sys.executable or 'python3'
    onboard: str = 'onboard'
    killall: str = 'killall'
    poweroff: str = 'poweroff'


@dataclass(frozen=True)
class SensorSettings:
    pin: int = 4
    humidity_offset: float = 15
    temperature_offset: float = -6


@dataclass(frozen=True)
class AppConfig:
    test_mode: bool = TEST
    settings_path: Path = Path.home() / '.config' / 'mulita' / 'settings.json'
    virtual_keyboard: bool = True
    capture_dir: PurePosixPath = Path.home() / 'capturas'
    default_capture_name: str = 'prueba'
    trace_dir: PurePosixPath = Path.home() / 'capturas' / 'trazas'
    ping_dir: PurePosixPath = Path.home() / 'capturas' / 'ping'
    wifi_dir: PurePosixPath = Path.home() / 'capturas' / 'wifi'
    scan_dir: PurePosixPath = Path.home() / 'capturas' / 'escaneo'
    nmap_dir: PurePosixPath = Path.home() / 'capturas' / 'nmap'
    discovery_dir: PurePosixPath = Path.home() / 'capturas' / 'descubrimiento'
    tls_dir: PurePosixPath = Path.home() / 'capturas' / 'tls'
    # Archivos que ve el tecnico: carpeta del TFTP, carpeta del servidor web y registros.
    servers_dir: PurePosixPath = Path.home() / 'capturas' / 'servidores'
    # Claves, certificados y estado interno. Fuera de las capturas para que no se compartan.
    servers_state_dir: Path = Path.home() / '.config' / 'mulita' / 'servers'
    trace_cycles: int = 6
    public_ip_url: str = 'https://ipwho.is/'
    public_ip_timeout: int = 10
    public_ip_dir: PurePosixPath = Path.home() / 'capturas' / 'internet'
    mac_vendor_url: str = 'https://api.macvendors.com'
    mac_vendor_timeout: int = 10
    repository_dir: str = str(PROJECT_ROOT)
    installation_user: str = ''
    # Puerto de la red interna. La IP se aplica con NetworkManager.
    internal_interface: str = 'eth0'
    internal_connection: str = 'mulita-interna'
    update_remote: str = 'origin'
    update_branch: str = 'v3'
    service_name: str = 'mulita'
    binaries: Binaries = field(default_factory=Binaries)
    sensor: SensorSettings = field(default_factory=SensorSettings)


def load_config(argv: Sequence[str] = ()) -> AppConfig:
    """`--test` o MULITA_TEST=1 activan el modo test;
    `--no-keyboard` desactiva el teclado virtual integrado de Qt."""
    test_mode = TEST or '--test' in argv or os.environ.get('MULITA_TEST') == '1'
    paths = _installation_paths()
    return AppConfig(**paths, test_mode=test_mode,
                     virtual_keyboard='--no-keyboard' not in argv)


def _installation_paths() -> dict:
    """Las rutas instaladas no dependen del HOME del servicio root."""
    configured = os.environ.get('MULITA_CONFIG')
    path = Path(configured) if configured else Path('/etc/mulita/config.json')
    data = {}
    if configured or os.name == 'posix':
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            if configured:
                raise ValueError(f'No existe la configuración de Mulita: {path}')
        except (OSError, ValueError) as exc:
            raise ValueError(f'No se pudo leer la configuración de Mulita: {path}') from exc
    if not isinstance(data, dict):
        raise ValueError(f'Configuración de Mulita inválida: {path}')
    user = data.get('user', '')
    if not isinstance(user, str) or user.startswith('-') or any(char in user for char in '\n\r\x00'):
        raise ValueError(f'Usuario de instalación inválido en {path}')
    def directory(key, default):
        value = data.get(key, str(default))
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError(f'La ruta {key} debe ser absoluta en {path}')
        return Path(value)
    home = directory('user_home', Path.home())
    captures = directory('capture_dir', home / 'capturas')
    state = directory('state_dir', home / '.config' / 'mulita')
    return dict(capture_dir=captures, trace_dir=captures / 'trazas',
                ping_dir=captures / 'ping', wifi_dir=captures / 'wifi',
                scan_dir=captures / 'escaneo', nmap_dir=captures / 'nmap',
                discovery_dir=captures / 'descubrimiento', tls_dir=captures / 'tls',
                servers_dir=captures / 'servidores', public_ip_dir=captures / 'internet',
                settings_path=state / 'settings.json', servers_state_dir=state / 'servers',
                repository_dir=str(PROJECT_ROOT), installation_user=user)
