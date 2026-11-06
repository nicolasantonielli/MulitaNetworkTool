from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Sequence
from mulita.core.binaries import Binaries  # noqa: F401  (se reexporta: `from mulita.config import Binaries`)
from mulita.core.storage import StoragePaths

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Modo test en aplicacion
# Desactiva Sensor de temperatura
# Desactiva Fullscreen
TEST = False


@dataclass(frozen=True)
class SensorSettings:
    pin: int = 4
    humidity_offset: float = 15
    temperature_offset: float = -6


@dataclass(frozen=True)
class AppConfig:
    test_mode: bool = TEST
    settings_path: Path = field(default_factory=lambda: Path.home() / '.config' / 'mulita' / 'settings.json')
    virtual_keyboard: bool = True
    capture_dir: PurePosixPath = field(default_factory=lambda: Path.home() / 'capturas')
    storage: StoragePaths = field(init=False)
    default_capture_name: str = 'prueba'
    # Claves, certificados y estado interno. Fuera de las capturas para que no se compartan.
    servers_state_dir: Path = field(default_factory=lambda: Path.home() / '.config' / 'mulita' / 'servers')
    trace_cycles: int = 6
    public_ip_url: str = 'https://ipwho.is/'
    public_ip_timeout: int = 10
    mac_vendor_url: str = 'https://api.macvendors.com'
    mac_vendor_timeout: int = 10
    repository_dir: str = str(PROJECT_ROOT)
    installation_user: str = ''
    # Puerto de la red interna. La IP se aplica con NetworkManager.
    internal_interface: str = 'eth0'
    internal_connection: str = 'mulita-interna'
    update_remote: str = 'origin'
    update_branch: str = 'v3.1'
    service_name: str = 'mulita'
    binaries: Binaries = field(default_factory=Binaries)
    sensor: SensorSettings = field(default_factory=SensorSettings)

    def __post_init__(self):
        object.__setattr__(self, 'storage', StoragePaths(self.capture_dir))

    @property
    def trace_dir(self) -> PurePosixPath:
        return self.storage.folder('traza')

    @property
    def ping_dir(self) -> PurePosixPath:
        return self.storage.folder('ping')

    @property
    def wifi_dir(self) -> PurePosixPath:
        return self.storage.folder('wifi')

    @property
    def scan_dir(self) -> PurePosixPath:
        return self.storage.folder('escaneo')

    @property
    def nmap_dir(self) -> PurePosixPath:
        return self.storage.folder('nmap')

    @property
    def discovery_dir(self) -> PurePosixPath:
        return self.storage.folder('descubrimiento')

    @property
    def tls_dir(self) -> PurePosixPath:
        return self.storage.folder('tls')

    @property
    def servers_dir(self) -> PurePosixPath:
        return self.storage.folder('servidores')

    @property
    def public_ip_dir(self) -> PurePosixPath:
        return self.storage.folder('publica')


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
    return dict(capture_dir=captures,
                settings_path=state / 'settings.json', servers_state_dir=state / 'servers',
                repository_dir=str(PROJECT_ROOT), installation_user=user)
