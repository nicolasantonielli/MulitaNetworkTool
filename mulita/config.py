from __future__ import annotations

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
    python: str = sys.executable or 'python3'
    onboard: str = 'onboard'
    killall: str = 'killall'
    poweroff: str = 'poweroff'


@dataclass(frozen=True)
class SensorSettings:
    pin: int = 4
    humidity_offset: float = 15
    temperature_offset: float = -6


class Toolkit:
    QT = 'qt'
    TK = 'tk'


@dataclass(frozen=True)
class AppConfig:
    test_mode: bool = TEST
    toolkit: str = Toolkit.QT
    settings_path: Path = Path.home() / '.config' / 'mulita' / 'settings.json'
    virtual_keyboard: bool = True
    window_title: str = 'RED TEST'
    window_width: int = 800
    window_height: int = 480
    default_theme: str = 'cosmo'
    themes: tuple[str, ...] = (
        'cosmo', 'darkly', 'pulse', 'lumen', 'litera',
        'journal', 'solar', 'superhero', 'vapor', 'cyborg')
    capture_dir: PurePosixPath = PurePosixPath('/root/capturas')
    default_capture_name: str = 'prueba'
    trace_dir: PurePosixPath = PurePosixPath('/root/capturas/trazas')
    ping_dir: PurePosixPath = PurePosixPath('/root/capturas/ping')
    wifi_dir: PurePosixPath = PurePosixPath('/root/capturas/wifi')
    scan_dir: PurePosixPath = PurePosixPath('/root/capturas/escaneo')
    discovery_dir: PurePosixPath = PurePosixPath('/root/capturas/descubrimiento')
    tls_dir: PurePosixPath = PurePosixPath('/root/capturas/tls')
    # Archivos que ve el tecnico: carpeta del TFTP, carpeta del servidor web y registros.
    servers_dir: PurePosixPath = PurePosixPath('/root/capturas/servidores')
    # Claves, certificados y estado interno. Fuera de las capturas para que no se compartan.
    servers_state_dir: Path = Path.home() / '.config' / 'mulita' / 'servers'
    trace_cycles: int = 6
    public_ip_url: str = 'https://ipwho.is/'
    public_ip_timeout: int = 10
    public_ip_dir: PurePosixPath = PurePosixPath('/root/capturas/internet')
    mac_vendor_url: str = 'https://api.macvendors.com'
    mac_vendor_timeout: int = 10
    repository_dir: str = '/root/repositorio/MulitaNetworkTool'
    # Puerto de la red interna. La IP se aplica con NetworkManager.
    internal_interface: str = 'eth0'
    internal_connection: str = 'mulita-interna'
    update_remote: str = 'origin'
    update_branch: str = 'v3'
    service_name: str = 'mulita'
    assets_dir: Path = PROJECT_ROOT / 'img'
    binaries: Binaries = field(default_factory=Binaries)
    sensor: SensorSettings = field(default_factory=SensorSettings)


def load_config(argv: Sequence[str] = ()) -> AppConfig:
    """`--test` o MULITA_TEST=1 activan el modo test; `--tk` vuelve a la interfaz anterior;
    `--no-keyboard` desactiva el teclado virtual integrado."""
    test_mode = TEST or '--test' in argv or os.environ.get('MULITA_TEST') == '1'
    toolkit = Toolkit.TK if '--tk' in argv else Toolkit.QT
    return AppConfig(test_mode=test_mode, toolkit=toolkit,
                     virtual_keyboard='--no-keyboard' not in argv)
