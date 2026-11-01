"""Guarda las rutas de instalacion y genera la unidad systemd con rutas reales."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import tempfile

UNIT = """[Unit]
Description=Mulita Network Tool
After=systemd-user-sessions.service systemd-udev-trigger.service
Conflicts=getty@tty1.service
Before=getty@tty1.service

[Service]
Type=simple
WorkingDirectory={repository}
Environment=QT_QPA_PLATFORM=eglfs
Environment=QT_QPA_EGLFS_INTEGRATION=eglfs_kms
Environment={home}
Environment={config}
ExecStart={python} main.py
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
"""


def quoted(value: str, executable: bool = False) -> str:
    if any(char in value for char in ('\n', '\r', '\x00')):
        raise ValueError('Ruta con caracteres de control')
    value = value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    if executable:
        value = value.replace('$', '$$')
    return '"' + value + '"'


def unit_text(repository: Path, home: Path, config: Path) -> str:
    return UNIT.format(repository=quoted(str(repository)), home=quoted('HOME=' + str(home)),
                       config=quoted('MULITA_CONFIG=' + str(config)),
                       python=quoted(str(repository / '.venv/bin/python'), True))


def installation_config(repository: Path, user: str, home: Path, existing: dict,
                        capture: Path | None = None, state: Path | None = None,
                        legacy_home: Path | None = None) -> dict:
    def previous(key, default):
        value = existing.get(key, str(default))
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError(f'Ruta invalida: {key}')
        return Path(value)
    captures = home / 'capturas'
    settings = home / '.config' / 'mulita'
    if legacy_home is not None:
        if (legacy_home / 'capturas').is_dir():
            captures = legacy_home / 'capturas'
        if (legacy_home / '.config/mulita').is_dir():
            settings = legacy_home / '.config/mulita'
    captures = capture or previous('capture_dir', captures)
    settings = state or previous('state_dir', settings)
    if not captures.is_absolute() or not settings.is_absolute():
        raise ValueError('Las rutas deben ser absolutas')
    if captures == settings or captures in settings.parents or settings in captures.parents:
        raise ValueError('Las capturas y el estado privado deben estar en carpetas separadas')
    return dict(user=user, user_home=str(home), repository_dir=str(repository),
                capture_dir=str(captures), state_dir=str(settings))


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.mulita-', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main():
    import pwd
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--user', required=True)
    parser.add_argument('--capture-dir', type=Path)
    parser.add_argument('--state-dir', type=Path)
    args = parser.parse_args()
    account = pwd.getpwnam(args.user)
    home = Path(account.pw_dir)
    repository = args.repository.resolve(strict=True)
    path = Path('/etc/mulita/config.json')
    existing = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not isinstance(existing, dict):
        raise ValueError('Configuracion de instalacion invalida')
    legacy = Path(pwd.getpwnam('root').pw_dir)
    data = installation_config(repository, args.user, home, existing,
                               args.capture_dir, args.state_dir, legacy)
    for key, mode in (('capture_dir', 0o755), ('state_dir', 0o700)):
        directory = Path(data[key])
        if not directory.exists():
            directory.mkdir(parents=True, mode=mode)
            os.chown(directory, account.pw_uid, account.pw_gid)
    write_atomic(path, json.dumps(data, indent=2) + '\n')
    write_atomic(Path('/etc/systemd/system/mulita.service'), unit_text(repository, home, path))
    print('Rutas de Mulita guardadas en ' + str(path))
    print(json.dumps(data, indent=2))


if __name__ == '__main__':
    main()
