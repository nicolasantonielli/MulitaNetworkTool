from __future__ import annotations

import csv
import ipaddress
import os
import secrets
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Optional

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import AlreadyRunningError, CommandFailedError, ValidationError
from mulita.core.parsers import parse_default_gateway, parse_interface_ipv4
from mulita.core.ports import CommandRunner, ExitListener, OutputListener
from mulita.core.servers import KINDS, NO, YES, kind_by_id
from mulita.presentation.i18n import tr
from mulita.services.base import ProcessSession

USER_MARK = 'Mulita SFTP temporal'
UPLOADS = 'respaldos'
PASSWORD_ALPHABET = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
PASSWORD_LENGTH = 8


def suggest_password() -> str:
    return ''.join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))


@dataclass
class _Plan:
    argv: list[str]
    cleanup: Optional[Callable[[], None]] = None


class _Session(ProcessSession):

    def launch(self, argv, on_output, on_exit) -> None:
        self._launch(argv, on_output, on_exit)


class ServerService:
    """Arma y lanza cada servidor. Puede haber varios activos a la vez, uno por tipo."""

    def __init__(self, runner: CommandRunner, commands: CommandFactory,
                 servers_dir: PurePosixPath | Path, state_dir: Path,
                 capture_dir: PurePosixPath | Path, posix: bool | None = None):
        self._runner = runner
        self._commands = commands
        self._servers_dir = Path(servers_dir)
        self._state_dir = Path(state_dir)
        self._capture_dir = capture_dir
        # En Windows las rutas /root no existen: no se crean carpetas fuera de la Pi.
        self._posix = os.name == 'posix' if posix is None else posix
        self._sessions = {kind.id: _Session(runner, kind.title) for kind in KINDS}
        self._cleanups: dict[str, Callable[[], None]] = {}
        self._builders: dict[str, Callable[[Mapping[str, str]], _Plan]] = {
            'iperf': self._iperf, 'tftp': self._tftp, 'sftp': self._sftp, 'web': self._web,
            'dns': self._dns, 'dhcp': self._dhcp, 'ntp': self._ntp,
        }

    # --- Ciclo de vida ------------------------------------------------------------------

    def is_running(self, kind: str) -> bool:
        return self._sessions[kind_by_id(kind).id].is_running

    def start(self, kind: str, values: Mapping[str, str],
              on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None) -> None:
        definition = kind_by_id(kind)
        session = self._sessions[definition.id]
        if session.is_running:
            raise AlreadyRunningError(tr('serverRunning', name=tr(definition.title)))
        merged = {**definition.defaults(), **{key: str(value) for key, value in values.items()}}
        plan = self._builders[definition.id](merged)
        if plan.cleanup:
            self._cleanups[definition.id] = plan.cleanup

        def finished(code: int) -> None:
            self._cleanup(definition.id)
            if on_exit:
                on_exit(code)

        try:
            session.launch(plan.argv, on_output, finished)
        except Exception:
            self._cleanup(definition.id)
            raise

    def stop(self, kind: str) -> None:
        identifier = kind_by_id(kind).id
        self._sessions[identifier].stop()
        self._cleanup(identifier)

    def stop_all(self) -> None:
        for kind in KINDS:
            self.stop(kind.id)

    def _cleanup(self, kind: str) -> None:
        action = self._cleanups.pop(kind, None)
        if action:
            action()

    # --- Registro guardado --------------------------------------------------------------

    def save(self, kind: str, rows: list[dict], filename: str) -> str:
        definition = kind_by_id(kind)
        if not rows:
            raise ValidationError(tr('serverNoRows'))
        name = validation.trace_filename(filename)
        folder = self._servers_dir / 'registros'
        self._make_dir(folder, 'serverFolder')
        path = folder / name
        if path.parent.resolve() != folder.resolve():
            raise ValidationError(tr('badStoredName'))
        if path.exists():
            raise ValidationError(tr('nameExists'))
        try:
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle, lineterminator='\n')
                writer.writerow([tr(column.title) for column in definition.columns])
                for row in rows:
                    writer.writerow([row.get(column.key, '') for column in definition.columns])
        except OSError as exc:
            raise CommandFailedError(tr('serverSaveFailed')) from exc
        if hasattr(os, 'sync'):
            os.sync()
        return name

    # --- Ajustes comunes ----------------------------------------------------------------

    def _make_dir(self, path: Path, message: str) -> None:
        if not self._posix:
            return
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(tr(message)) from exc

    def _interface(self, values: Mapping[str, str], required: bool) -> tuple[str, str, int]:
        """Interfaz elegida, su direccion IPv4 y el prefijo. Vacia si el servidor escucha en todas."""
        name = (values.get('iface') or '').strip()
        if not name:
            if required:
                raise ValidationError(tr('serverNeedIface'))
            return '', '', 24
        name = validation.interface_name(name)
        result = self._runner.run(self._commands.interface_ipv4(name))
        address, prefix = parse_interface_ipv4(result.stdout) if result.ok else ('', 24)
        if not address:
            raise ValidationError(tr('serverNoAddress', interface=name))
        return name, address, prefix

    @staticmethod
    def _flag(values: Mapping[str, str], key: str) -> bool:
        return str(values.get(key, NO)).strip() == YES

    def _port(self, values: Mapping[str, str], key: str = 'port', label: str = 'fieldPort') -> int:
        return validation.port_number(values.get(key, ''), tr(label))

    def _folder(self, name: str) -> Path:
        path = self._servers_dir / name
        self._make_dir(path, 'serverFolder')
        return path

    def _state(self, name: str) -> Path:
        path = self._state_dir / name
        self._make_dir(path, 'serverFolder')
        return path

    # --- Servidores ---------------------------------------------------------------------

    def _iperf(self, values: Mapping[str, str]) -> _Plan:
        _name, address, _prefix = self._interface(values, required=False)
        return _Plan(self._commands.iperf_server(self._port(values), address, self._flag(values, 'once')))

    def _tftp(self, values: Mapping[str, str]) -> _Plan:
        _name, address, _prefix = self._interface(values, required=False)
        root = self._folder('tftp')
        return _Plan(self._commands.tftp_server(
            str(root), self._port(values), address, self._flag(values, 'writable')))

    def _ntp(self, values: Mapping[str, str]) -> _Plan:
        _name, address, _prefix = self._interface(values, required=False)
        stratum = validation.integer_between(values.get('stratum', ''), 1, 15, tr('serverStratum'))
        return _Plan(self._commands.ntp_server(self._port(values), stratum, address))

    def _web(self, values: Mapping[str, str]) -> _Plan:
        _name, address, _prefix = self._interface(values, required=False)
        mode = values.get('mode', 'http')
        if mode not in ('http', 'https', 'both'):
            raise ValidationError(tr('badMode', value=mode))
        http_port = self._port(values, 'http_port', 'serverHttpPort') if mode != 'https' else 0
        https_port = self._port(values, 'https_port', 'serverHttpsPort') if mode != 'http' else 0
        if http_port and http_port == https_port:
            raise ValidationError(tr('serverPortsEqual'))
        certificate = key = ''
        if https_port:
            certificate, key = self._certificate()
        captures = str(self._capture_dir) if self._flag(values, 'share') else ''
        return _Plan(self._commands.web_server(
            str(self._folder('web')), http_port, https_port, address, captures, certificate, key))

    def _certificate(self) -> tuple[str, str]:
        folder = self._state('web')
        certificate, key = folder / 'cert.pem', folder / 'key.pem'
        if self._posix and not (certificate.exists() and key.exists()):
            result = self._runner.run(self._commands.tls_certificate(str(certificate), str(key)))
            if not result.ok:
                raise CommandFailedError(tr('serverPrepare', detail=_first_line(result.text)), result)
        return str(certificate), str(key)

    def _dns(self, values: Mapping[str, str]) -> _Plan:
        _name, address, _prefix = self._interface(values, required=True)
        name = validation.dns_name(values.get('name', ''))
        answer_text = (values.get('answer') or '').strip()
        answer = validation.ipv4_address(answer_text, tr('serverAnswer')) if answer_text else address
        upstream_text = (values.get('upstream') or '').strip()
        upstream = validation.ipv4_address(upstream_text, tr('serverUpstream')) if upstream_text else ''
        pid = self._state('dns') / 'dnsmasq.pid'
        return _Plan(self._commands.dns_server(
            address, self._port(values), name, answer, upstream, str(pid)))

    def _dhcp(self, values: Mapping[str, str]) -> _Plan:
        name, address, prefix = self._interface(values, required=True)
        route = self._runner.run(self._commands.interface_gateway(name))
        if route.ok and parse_default_gateway(route.stdout):
            raise ValidationError(tr('dhcpUplink', interface=name))
        network = ipaddress.IPv4Network(f'{address}/{prefix}', strict=False)
        if network.prefixlen > 29:
            raise ValidationError(tr('dhcpSmallNet', interface=name))
        first, last = _dhcp_range(network, address, values)
        gateway = _optional_ip(values.get('gateway'), tr('fieldGateway'), address)
        dns = _optional_ip(values.get('dns'), 'DNS', address)
        hours = validation.integer_between(values.get('hours', ''), 1, 168, tr('serverLease'))
        folder = self._state('dhcp')
        return _Plan(self._commands.dhcp_server(
            name, first, last, str(network.netmask), hours, gateway, dns,
            str(folder / 'dnsmasq.leases'), str(folder / 'dnsmasq.pid')))

    def _sftp(self, values: Mapping[str, str]) -> _Plan:
        _name, address, _prefix = self._interface(values, required=False)
        port = self._port(values)
        user = validation.system_user(values.get('user', ''))
        password = validation.temporary_password(values.get('password', ''))
        writable = self._flag(values, 'writable')

        entry = self._runner.run(self._commands.user_entry(user))
        if entry.ok and entry.stdout.strip():
            if USER_MARK not in entry.stdout:
                raise ValidationError(tr('sftpUserTaken', user=user))
        else:
            self._must(self._commands.user_add(user, USER_MARK))

        uploads = PurePosixPath(self._capture_dir) / UPLOADS

        def cleanup() -> None:
            # Las subidas quedan a nombre de root: un usuario nuevo con otro numero no las pierde.
            self._runner.run(self._commands.change_owner('root:root', str(uploads), recursive=True))
            self._runner.run(self._commands.user_delete(user))

        try:
            self._make_dir(Path(uploads), 'serverFolder')
            folder = self._state('sftp')
            host_key = folder / 'host_ed25519'
            if self._posix and not host_key.exists():
                self._must(self._commands.ssh_host_key(str(host_key)))
            config = folder / 'sshd_config'
            self._write_sshd_config(config, host_key, port, address, user, writable)
            self._must(self._commands.set_password(), f'{user}:{password}\n')
            self._must(self._commands.change_owner(user, str(uploads), recursive=True))
            if self._posix:
                Path('/run/sshd').mkdir(mode=0o755, parents=True, exist_ok=True)
        except Exception:
            cleanup()
            raise
        return _Plan(self._commands.sftp_server(str(config)), cleanup)

    def _write_sshd_config(self, path: Path, host_key: Path, port: int, address: str,
                           user: str, writable: bool) -> None:
        lines = [f'Port {port}']
        if address:
            lines.append(f'ListenAddress {address}')
        lines += [
            f'HostKey {host_key}', 'PidFile none', 'UsePAM no', 'LogLevel VERBOSE',
            'LoginGraceTime 30', 'MaxAuthTries 3', 'PermitRootLogin no',
            'PasswordAuthentication yes', 'PubkeyAuthentication no',
            'ChallengeResponseAuthentication no', f'AllowUsers {user}',
            'AllowTcpForwarding no', 'X11Forwarding no', 'PermitTTY no',
            'Subsystem sftp internal-sftp',
            f'Match User {user}',
            f'    ChrootDirectory {self._capture_dir}',
            f'    ForceCommand internal-sftp{"" if writable else " -R"}',
        ]
        if not self._posix:
            return
        try:
            path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        except OSError as exc:
            raise CommandFailedError(tr('serverFolder')) from exc

    def _must(self, argv: list[str], input_text: str | None = None) -> None:
        result = (self._runner.run(argv, input_text=input_text) if input_text is not None
                  else self._runner.run(argv))
        if not result.ok:
            raise CommandFailedError(tr('serverPrepare', detail=_first_line(result.text)), result)


def _first_line(text: str) -> str:
    return next((line.strip() for line in (text or '').splitlines() if line.strip()), '')[:180]


def _optional_ip(value: str | None, field: str, default: str) -> str:
    text = (value or '').strip()
    return validation.ipv4_address(text, field) if text else default


def _dhcp_range(network: ipaddress.IPv4Network, address: str,
                values: Mapping[str, str]) -> tuple[str, str]:
    base, top = int(network.network_address), int(network.broadcast_address)
    hosts = top - base - 1
    own = int(ipaddress.IPv4Address(address))
    start = base + min(100, max(2, hosts // 2))
    end = min(start + 50, top - 1)
    first_text = (values.get('first') or '').strip()
    last_text = (values.get('last') or '').strip()
    first = int(ipaddress.IPv4Address(validation.ipv4_address(first_text, tr('serverFrom')))) if first_text else start
    last = int(ipaddress.IPv4Address(validation.ipv4_address(last_text, tr('serverTo')))) if last_text else end
    if first_text and not last_text:
        last = min(first + 50, top - 1)
    if last_text and not first_text:
        first = max(base + 1, last - 50)
    inside = base < first <= last < top
    if not inside or first <= own <= last:
        raise ValidationError(tr('dhcpRange'))
    return str(ipaddress.IPv4Address(first)), str(ipaddress.IPv4Address(last))
