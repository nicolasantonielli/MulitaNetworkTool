"""Escaneo Nmap: un proceso por vez, informe en su propia carpeta y perfiles propios."""
from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath

from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.models import MISSING_COMMAND_CODE
from mulita.core.nmapscan import (Compiled, compare_scans, compile_scan, open_tcp_ports,
                                  parse_xml, privilege_error, saved_arguments)
from mulita.core.ports import CommandRunner, ExitListener, OutputListener
from mulita.presentation.i18n import tr
from mulita.services.base import ProcessSession

_RUN = re.compile(r'^[0-9]{8}-[0-9]{6}(?:-\d+)?$')
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
_PLACES = {
    'captura': '',
    'tap': 'tap',
    'traza': 'trazas',
    'ping': 'ping',
    'publica': 'internet',
    'wifi': 'wifi',
    'escaneo': 'escaneo',
    'descubrimiento': 'descubrimiento',
    'tls': 'tls',
    'servidores': 'servidores',
    'nmap': 'nmap',
}
_PLACE_LABEL = {
    'captura': 'placeCapture', 'tap': 'placeTap', 'traza': 'placeTrace', 'ping': 'placePing',
    'publica': 'placePublic', 'wifi': 'placeWifi', 'escaneo': 'placeScan',
    'descubrimiento': 'placeDiscover', 'tls': 'placeTls', 'servidores': 'pageServers',
    'nmap': 'cyberNmap',
}


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
                 directory: PurePosixPath | Path = PurePosixPath('/root/capturas/nmap'),
                 state_dir: Path | None = None,
                 capture_dir: PurePosixPath | Path = PurePosixPath('/root/capturas')):
        super().__init__(runner, 'El escaneo')
        self._commands = commands
        self._directory = Path(directory)
        self._state = Path(state_dir) if state_dir else Path.home() / '.config' / 'mulita' / 'nmap'
        self._captures = Path(capture_dir)
        self.version = ''
        self.outcome: Outcome | None = None
        self._known: set[str] = set()
        self._active: Path | None = None
        self._cancel = False
        self._stdout: list[str] = []
        self._stderr: list[str] = []

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

    def launch(self, prepared: Prepared, on_output: OutputListener | None = None,
               on_exit: ExitListener | None = None) -> None:
        xml = prepared.folder / 'informe.xml'
        normal = prepared.folder / 'salida.txt'
        args = list(prepared.compiled.args)
        count = prepared.compiled.target_count
        head, tail = (args[:-count], args[-count:]) if count else (args, [])
        argv = self._commands.nmap([*head, '-oX', str(xml), '-oN', str(normal), *tail])
        self._stdout = []
        self._stderr = []
        self._active = prepared.folder
        self.outcome = None

        def emit(text: str) -> None:
            if on_output:
                on_output(text)

        def finished(code: int) -> None:
            self._finish(prepared, code)
            if on_exit:
                on_exit(code)

        self._launch(argv, lambda text: self._keep(self._stdout, text, emit), finished,
                     lambda text: self._keep(self._stderr, text, emit), group=True)

    def request_cancel(self) -> None:
        self._cancel = True

    def discard(self, prepared: Prepared) -> None:
        """El usuario canceló antes de que el proceso arrancara."""
        self._write_meta(prepared, 'cancelled', None, True)

    def load(self, run_id: str, today: date | None = None) -> tuple[dict, tuple[dict, ...]]:
        folder = self._folder(run_id)
        meta = self._read_meta(folder)
        document = parse_xml(self._read_text(folder / 'informe.xml'), today or date.today())
        return meta, document.hosts

    def compare(self, first: str, second: str, today: date | None = None) -> dict:
        _meta, before = self.load(first, today)
        _other, after = self.load(second, today)
        return compare_scans(list(before), list(after))

    def history(self) -> list[dict]:
        if not self._directory.is_dir():
            return []
        found = []
        active = self._active
        for child in self._directory.iterdir():
            if not child.is_dir() or not (child / 'meta.json').is_file():
                continue
            item = self._read_meta(child)
            if item.get('status') == 'running' and child != active:
                item['status'] = 'incomplete'
            found.append({key: item.get(key, '') for key in (
                'id', 'profile', 'command', 'targets', 'started', 'finished', 'status',
                'partial', 'simulated', 'nmapVersion')})
        found.sort(key=lambda item: item.get('started', ''), reverse=True)
        return found[:40]

    def users(self) -> list[dict]:
        try:
            data = json.loads((self._state / 'profiles.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict) and str(item.get('id', '')).startswith('user-')]

    def save_user(self, profile_id: str, name: str, description: str, arguments: str) -> dict:
        clean = _profile_name(name)
        line = _saved_line(arguments)
        about = (description or '').strip()
        if len(about) > 240:
            raise ValidationError(tr('nmapBadName'))
        items = self.users()
        if profile_id.startswith('user-') and any(item['id'] == profile_id for item in items):
            saved = {'id': profile_id, 'name': clean, 'description': about, 'arguments': line}
            items = [saved if item['id'] == profile_id else item for item in items]
        else:
            number = 1 + max((int(item['id'].split('-', 1)[1]) for item in items
                              if item['id'].split('-', 1)[-1].isdigit()), default=0)
            saved = {'id': f'user-{number}', 'name': clean, 'description': about, 'arguments': line}
            items.append(saved)
        self._write_users(items)
        return saved

    def delete_user(self, profile_id: str) -> None:
        items = [item for item in self.users() if item['id'] != profile_id]
        if len(items) == len(self.users()):
            raise ValidationError(tr('nmapBadProfile', value=profile_id))
        self._write_users(items)

    def duplicate_user(self, profile_id: str) -> dict:
        source = next((item for item in self.users() if item['id'] == profile_id), None)
        if source is None:
            raise ValidationError(tr('nmapBadProfile', value=profile_id))
        return self.save_user('', f"{source['name']} {tr('nmapCopy')}", source.get('description', ''),
                              source.get('arguments', ''))

    def list_files(self) -> list[dict]:
        found = []
        if not self._captures.is_dir():
            return found
        for place, folder in _PLACES.items():
            base = self._captures / folder if folder else self._captures
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
            folder = _PLACES[place]
            base = self._captures / folder if folder else self._captures
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
            raise CommandFailedError(tr('nmapMissing'))
        found = _VERSION.search(result.stdout or '')
        self.version = found.group(1) if found else ''
        if result.returncode != 0 and not self.version:
            raise CommandFailedError((result.text or '').strip() or tr('nmapMissing'))

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
            raise CommandFailedError(tr('nmapScriptMissing', names=', '.join(missing)))

    def _finish(self, prepared: Prepared, code: int) -> None:
        folder = prepared.folder
        self._write_text(folder / 'progreso.txt', ''.join(self._stdout))
        self._write_text(folder / 'errores.txt', ''.join(self._stderr))
        document = parse_xml(self._read_text(folder / 'informe.xml'), prepared.today)
        self._write_csv(folder, document.hosts)
        streamed = ''.join(self._stdout + self._stderr)
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
        lines = [line.strip() for line in streamed.splitlines() if line.strip()]
        self.outcome = Outcome(
            document.hosts, status, partial or document.partial, prepared.compiled.command,
            prepared.compiled.profile_id, code, privilege_error(streamed),
            open_tcp_ports(document.hosts), '\n'.join(lines[-8:]), folder.name)
        self._active = None
        if hasattr(os, 'sync'):
            os.sync()

    def _write_csv(self, folder: Path, hosts: tuple[dict, ...]) -> None:
        path = folder / 'puertos.csv'
        with path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle, lineterminator='\n')
            writer.writerow([
                tr('nmapHost'), tr('nmapNames'), tr('nmapState'), tr('nmapMac'), tr('nmapVendor'),
                tr('nmapOs'), tr('scanPort'), tr('scanProto'), tr('nmapPortState'), tr('nmapReason'),
                tr('scanService'), tr('nmapProduct'), tr('nmapDetectedVersion'), tr('nmapScripts'),
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
        current = self._read_meta(prepared.folder) if path.is_file() else {}
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

    def _folder(self, run_id: str) -> Path:
        if not _RUN.fullmatch(run_id or ''):
            raise ValidationError(tr('nmapRunMissing'))
        folder = self._directory / run_id
        if not folder.is_dir() or folder.parent.resolve() != self._directory.resolve():
            raise ValidationError(tr('nmapRunMissing'))
        return folder

    def _read_meta(self, folder: Path) -> dict:
        try:
            data = json.loads((folder / 'meta.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {'id': folder.name}
        return data if isinstance(data, dict) else {'id': folder.name}

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            return ''

    @staticmethod
    def _write_text(path: Path, text: str) -> None:
        path.write_text(text, encoding='utf-8')

    def _write_users(self, items: list[dict]) -> None:
        self._mkdir(self._state)
        self._write_text(self._state / 'profiles.json', json.dumps(items, ensure_ascii=False, indent=2))

    @staticmethod
    def _mkdir(folder: Path) -> None:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(tr('nmapFolder')) from exc

    @staticmethod
    def _keep(sink: list[str], text: str, emit) -> None:
        sink.append(text)
        emit(text)


def _label(state: str) -> str:
    key = _STATE.get(state)
    return tr(key) if key else state


def _profile_name(name: str) -> str:
    clean = ' '.join((name or '').split())
    if not clean or len(clean) > 40:
        raise ValidationError(tr('nmapBadName'))
    return clean


def _saved_line(arguments: str) -> str:
    return saved_arguments(arguments)
