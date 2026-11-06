"""Escaneo Nmap: un proceso por vez, informe en su propia carpeta y perfiles propios."""
from __future__ import annotations

from mulita.services.operation_events import session

from mulita.core.storage import PLACES, StoragePaths

import csv
import json
import os
import re
import threading
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath

from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError
from mulita.core.models import MISSING_COMMAND_CODE
from mulita.core.nmapscan import (Compiled, compile_scan, open_tcp_ports,
                                  parse_xml, privilege_error)
from mulita.core.ports import CommandRunner, ExitListener, OutputListener
from mulita.core.messages import message
from mulita.services.base import ProcessSession
from mulita.services.nmap_profiles import NmapProfiles
from mulita.services.nmap_history import NmapHistory

_VERSION = re.compile(r'Nmap version (\S+)')
_STATE = {
    'open': 'nmapStateOpen',
    'closed': 'nmapStateClosed',
    'filtered': 'nmapStateFiltered',
    'open|filtered': 'nmapStateOpenFiltered',
    'closed|filtered': 'nmapStateClosedFiltered',
    'up': 'nmapStateUp',
    'down': 'nmapStateDown',
}
# Carpetas de capturas que se pueden elegir para -iL o --script. La pantalla muestra el nombre.
_PLACES = {place.id: place.folder for place in PLACES if place.nmap_input}
_PLACE_LABEL = {place.id: place.label for place in PLACES if place.nmap_input}


@dataclass
class Prepared:
    compiled: Compiled
    folder: Path
    simulated: bool
    today: date


@dataclass
class Outcome:
    hosts: tuple[dict, ...]
    status: str
    partial: bool
    command: str
    profile_id: str
    exit_code: int
    privilege: bool
    open_ports: str
    tail: str
    run_id: str


class NmapScanService(ProcessSession):

    def __init__(self, runner: CommandRunner, commands: CommandFactory,
                 directory: PurePosixPath | Path = Path.home() / 'capturas' / 'nmap',
                 state_dir: Path | None = None,
                 capture_dir: PurePosixPath | Path = Path.home() / 'capturas'):
        super().__init__(runner, 'El escaneo')
        self._commands = commands
        self._directory = Path(directory)
        self._state = Path(state_dir) if state_dir else Path.home() / '.config' / 'mulita' / 'nmap'
        self._profiles = NmapProfiles(self._state)
        self._history = NmapHistory(self._directory)
        self._captures = Path(capture_dir)
        self._paths = StoragePaths(self._captures)
        self.version = ''
        self.outcome: Outcome | None = None
        self._known: set[str] = set()
        self._active: Path | None = None
        self._cancel = False
        self._tail: deque[str] = deque(maxlen=8)
        self._privilege = False
        self._log_lock = threading.Lock()

    def users(self) -> list[dict]:
        return self._profiles.users()

    def save_user(self, profile_id: str, name: str, description: str, arguments: str) -> dict:
        return self._profiles.save_user(profile_id, name, description, arguments)

    def delete_user(self, profile_id: str) -> None:
        return self._profiles.delete_user(profile_id)

    def duplicate_user(self, profile_id: str) -> dict:
        return self._profiles.duplicate_user(profile_id)

    def load(self, run_id: str, today: date | None = None) -> tuple[dict, tuple[dict, ...]]:
        return self._history.load(run_id, today)

    def compare(self, first: str, second: str, today: date | None = None) -> dict:
        return self._history.compare(first, second, today)

    def history(self) -> list[dict]:
        return self._history.history(self._active)

    def probe(self) -> str:
        self._ensure_nmap()
        return self.version

    def reset_cancel(self) -> None:
        self._cancel = False

    def prepare(self, data: dict, simulated: bool = False, today: date | None = None) -> Prepared:
        self._ensure_nmap()
        compiled = compile_scan(data, {item['id']: item for item in self.users()}, self.resolve)
        self._ensure_scripts(compiled.scripts)
        folder = self._new_folder()
        prepared = Prepared(compiled, folder, simulated, today or date.today())
        self._write_meta(prepared, 'running', None, False)
        return prepared

    @session('nmap')
    def launch(self, prepared: Prepared, on_output: OutputListener | None = None,
               on_exit: ExitListener | None = None) -> None:
        xml = prepared.folder / 'informe.xml'
        normal = prepared.folder / 'salida.txt'
        args = list(prepared.compiled.args)
        count = prepared.compiled.target_count
        head, tail = (args[:-count], args[-count:]) if count else (args, [])
        argv = self._commands.nmap([*head, '-oX', str(xml), '-oN', str(normal), *tail])
        self._tail.clear()
        self._privilege = False
        progress_log = prepared.folder / 'progreso.txt'
        error_log = prepared.folder / 'errores.txt'
        self._write_text(progress_log, '')
        self._write_text(error_log, '')
        self._active = prepared.folder
        self.outcome = None

        def emit(text: str) -> None:
            if on_output:
                on_output(text)

        def finished(code: int) -> None:
            self._finish(prepared, code)
            if on_exit:
                on_exit(code)

        self._launch(argv, lambda text: self._keep(progress_log, text, emit), finished,
                     lambda text: self._keep(error_log, text, emit), group=True)

    def request_cancel(self) -> None:
        self._cancel = True

    def discard(self, prepared: Prepared) -> None:
        """El usuario canceló antes de que el proceso arrancara."""
        self._write_meta(prepared, 'cancelled', None, True)


    def list_files(self) -> list[dict]:
        found = []
        if not self._captures.is_dir():
            return found
        for place in _PLACES:
            base = self._paths.folder(place)
            if not base.is_dir():
                continue
            for child in sorted(base.iterdir(), key=lambda item: item.name.lower()):
                if child.is_file():
                    found.append({'name': child.name, 'place': _PLACE_LABEL.get(place, place),
                                  'token': f'@{place}/{child.name}'})
                if len(found) >= 80:
                    return found
        return found

    def resolve(self, value: str) -> str | None:
        if value.startswith('@'):
            place, _sep, name = value[1:].partition('/')
            if place not in _PLACES or not name or '/' in name or '\\' in name or name in ('.', '..'):
                return None
            base = self._paths.folder(place)
            path = base / name
            try:
                if path.is_file() and path.resolve().parent == base.resolve():
                    return str(path.resolve())
            except OSError:
                return None
            return None
        if '/' in value or '\\' in value:
            path = Path(value)
            try:
                if path.is_file():
                    return str(path.resolve())
            except OSError:
                return None
        return None

    def _ensure_nmap(self) -> None:
        binary = self._commands.nmap([])[0]
        result = self._runner.run([binary, '--version'], timeout=20)
        if result.returncode == MISSING_COMMAND_CODE:
            raise CommandFailedError(message('nmapMissing'))
        found = _VERSION.search(result.stdout or '')
        self.version = found.group(1) if found else ''
        if result.returncode != 0 and not self.version:
            raise CommandFailedError((result.text or '').strip() or message('nmapMissing'))

    def _ensure_scripts(self, scripts: tuple[str, ...]) -> None:
        missing = []
        binary = self._commands.nmap([])[0]
        for name in scripts:
            if '/' in name or '\\' in name or name in self._known:
                continue
            result = self._runner.run([binary, '--script-help', name], timeout=30)
            text = f'{result.stdout}\n{result.stderr}'
            if result.returncode != 0 or 'did not match' in text:
                missing.append(name)
            else:
                self._known.add(name)
        if missing:
            raise CommandFailedError(message('nmapScriptMissing', names=', '.join(missing)))

    def _finish(self, prepared: Prepared, code: int) -> None:
        folder = prepared.folder
        document = parse_xml(self._history.read_text(folder / 'informe.xml'), prepared.today)
        self._write_csv(folder, document.hosts)
        cancelled = self._cancel
        self._cancel = False
        if cancelled:
            status, partial = 'cancelled', not document.complete
        elif code == MISSING_COMMAND_CODE:
            status, partial = 'error', False
        elif document.complete and code == 0:
            status, partial = 'ok', False
        elif document.hosts:
            status, partial = 'partial', True
        else:
            status, partial = 'error', True
        self._write_meta(prepared, status, code, partial or document.partial)
        self.outcome = Outcome(
            document.hosts, status, partial or document.partial, prepared.compiled.command,
            prepared.compiled.profile_id, code, self._privilege,
            open_tcp_ports(document.hosts), '\n'.join(self._tail), folder.name)
        self._active = None
        if hasattr(os, 'sync'):
            os.sync()

    def _write_csv(self, folder: Path, hosts: tuple[dict, ...]) -> None:
        path = folder / 'puertos.csv'
        with path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle, lineterminator='\n')
            writer.writerow([
                'host', 'names', 'state', 'mac', 'vendor',
                'os', 'port', 'protocol', 'port_state', 'reason',
                'service', 'product', 'version', 'scripts',
            ])
            for host in hosts:
                ports = host['ports'] or [None]
                for port in ports:
                    scripts = host['scripts'] + (port['scripts'] if port else [])
                    writer.writerow([
                        host['ip'], ' '.join(host['names']), _label(host['state']), host['mac'],
                        host['vendor'], host['os'],
                        '' if port is None else port['port'],
                        '' if port is None else port['protocol'],
                        '' if port is None else _label(port['state']),
                        '' if port is None else port['reason'],
                        '' if port is None else port['service'],
                        '' if port is None else port['product'],
                        '' if port is None else port['version'],
                        ' | '.join(f"{item['id']}: {item['output']}" for item in scripts if item['output']),
                    ])

    def _write_meta(self, prepared: Prepared, status: str, code: int | None, partial: bool) -> None:
        path = prepared.folder / 'meta.json'
        current = self._history.read_meta(prepared.folder) if path.is_file() else {}
        compiled = prepared.compiled
        targets = compiled.display[-compiled.target_count:]
        current.update({
            'id': prepared.folder.name,
            'profile': compiled.profile_id,
            'command': compiled.command,
            'targets': ' '.join(targets),
            'started': current.get('started') or datetime.now().isoformat(timespec='seconds'),
            'finished': '' if status == 'running' else datetime.now().isoformat(timespec='seconds'),
            'status': status,
            'exitCode': code,
            'partial': partial,
            'nmapVersion': self.version,
            'simulated': prepared.simulated,
        })
        self._write_text(path, json.dumps(current, ensure_ascii=False, indent=2))

    def _new_folder(self) -> Path:
        self._mkdir(self._directory)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        folder = self._directory / stamp
        extra = 2
        while folder.exists():
            folder = self._directory / f'{stamp}-{extra}'
            extra += 1
        folder.mkdir()
        return folder


    @staticmethod
    def _write_text(path: Path, text: str) -> None:
        path.write_text(text, encoding='utf-8')


    @staticmethod
    def _mkdir(folder: Path) -> None:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(message('nmapFolder')) from exc

    def _keep(self, path: Path, text: str, emit) -> None:
        # Cada bloque queda escrito antes de notificar a la pantalla. Solo se
        # retiene una cola acotada para el mensaje final, no todo el escaneo.
        with self._log_lock:
            with path.open('a', encoding='utf-8') as handle:
                handle.write(text)
            self._privilege = self._privilege or privilege_error(text)
            for line in text.splitlines():
                if line.strip():
                    self._tail.append(line.strip()[-2048:])
        emit(text)


def _label(state: str) -> str:
    return state
