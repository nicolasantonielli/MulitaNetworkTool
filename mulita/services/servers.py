from __future__ import annotations

from mulita.core.events import EventSource
from mulita.services.operation_events import operation, session, stop_events

import csv
import ipaddress
import os
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Optional

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import AlreadyRunningError, CommandFailedError, ValidationError
from mulita.core.parsers import parse_default_gateway, parse_interface_ipv4
from mulita.core.ports import CommandRunner, ExitListener, OutputListener
from mulita.core.servers import KINDS, NO, YES, kind_by_id
from mulita.core.messages import message
from mulita.services.base import ProcessSession

from mulita.services.server_plan import ServerPlan as _Plan
from mulita.services.sftp_provisioning import SftpProvisioner, USER_MARK  # noqa: F401  (los tests lo importan desde aqui)
class _Session(ProcessSession):

    def launch(self, argv, on_output, on_exit) -> None:
        self._launch(argv, on_output, on_exit)


class ServerService(EventSource):
    """Arma y lanza cada servidor. Puede haber varios activos a la vez, uno por tipo."""

    def __init__(self, runner: CommandRunner, commands: CommandFactory,
                 servers_dir: PurePosixPath | Path, state_dir: Path,
                 capture_dir: PurePosixPath | Path, posix: bool | None = None,
                 settings_path: Path | None = None):
        self._runner = runner
        self._commands = commands
        self._servers_dir = Path(servers_dir)
        self._state_dir = Path(state_dir)
        self._capture_dir = capture_dir
        self._settings_path = settings_path
        # En Windows las rutas /root no existen: no se crean carpetas fuera de la Pi.
        self._posix = os.name == 'posix' if posix is None else posix
        self._sftp_provisioner = SftpProvisioner(runner, commands, self._state_dir, capture_dir, self._posix)
        self._sessions = {kind.id: _Session(runner, kind.title) for kind in KINDS}
        self._cleanups: dict[str, Callable[[], None]] = {}
        self._builders: dict[str, Callable[[Mapping[str, str]], _Plan]] = {
            'iperf': self._iperf, 'tftp': self._tftp, 'sftp': self._sftp, 'web': self._web,
            'dns': self._dns, 'dhcp': self._dhcp, 'ntp': self._ntp,
        }

    # --- Ciclo de vida ------------------------------------------------------------------

    def is_running(self, kind: str) -> bool:
        return self._sessions[kind_by_id(kind).id].is_running

    @session('server', 'kind')
    def start(self, kind: str, values: Mapping[str, str],
              on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None) -> None:
        definition = kind_by_id(kind)
        session = self._sessions[definition.id]
        if session.is_running:
            raise AlreadyRunningError(message('serverRunning', name=message(definition.title)))
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
        stop_events(self, identifier)
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

    @operation('export', context=lambda _: {'test': 'server'})
    def save(self, kind: str, rows: list[dict], filename: str) -> str:
        definition = kind_by_id(kind)
        if not rows:
            raise ValidationError(message('serverNoRows'))
        name = validation.trace_filename(filename)
        folder = self._servers_dir / 'registros'
        self._make_dir(folder, 'serverFolder')
        path = folder / name
        if path.parent.resolve() != folder.resolve():
            raise ValidationError(message('badStoredName'))
        if path.exists():
            raise ValidationError(message('nameExists'))
        try:
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle, lineterminator='\n')
                writer.writerow([column.key for column in definition.columns])
                for row in rows:
                    writer.writerow([row.get(column.key, '') for column in definition.columns])
        except OSError as exc:
            raise CommandFailedError(message('serverSaveFailed')) from exc
        if hasattr(os, 'sync'):
            os.sync()
        return name

    # --- Ajustes comunes ----------------------------------------------------------------

    def _make_dir(self, path: Path, error_key: str) -> None:
        if not self._posix:
            return
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(message(error_key)) from exc

    def _interface(self, values: Mapping[str, str], required: bool) -> tuple[str, str, int]:
        """Interfaz elegida, su direccion IPv4 y el prefijo. Vacia si el servidor escucha en todas."""
        name = (values.get('iface') or '').strip()
        if not name:
            if required:
                raise ValidationError(message('serverNeedIface'))
            return '', '', 24
        name = validation.interface_name(name)
        result = self._runner.run(self._commands.interface_ipv4(name))
        address, prefix = parse_interface_ipv4(result.stdout) if result.ok else ('', 24)
        if not address:
            raise ValidationError(message('serverNoAddress', interface=name))
        return name, address, prefix

    @staticmethod
    def _flag(values: Mapping[str, str], key: str) -> bool:
        return str(values.get(key, NO)).strip() == YES

    def _port(self, values: Mapping[str, str], key: str = 'port', label: str = 'fieldPort') -> int:
        return validation.port_number(values.get(key, ''), message(label))

    def _folder(self, name: str) -> Path:
        path = self._servers_dir / name
        self._make_dir(path, 'serverFolder')
        return path

    def _state(self, name: str) -> Path:
        path = self._state_dir / name
        self._make_dir(path, 'serverFolder')
        return path

    # --- Servidores ---------------------------------------------------------------------

    def _sftp(self, values: Mapping[str, str]) -> _Plan:
        _name, address, _prefix = self._interface(values, required=False)
        return self._sftp_provisioner.prepare(
            validation.system_user(values.get('user', '')),
            validation.temporary_password(values.get('password', '')),
            self._flag(values, 'writable'), self._port(values), address)

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
        stratum = validation.integer_between(values.get('stratum', ''), 1, 15, message('serverStratum'))
        return _Plan(self._commands.ntp_server(self._port(values), stratum, address))

    def _web(self, values: Mapping[str, str]) -> _Plan:
        _name, address, _prefix = self._interface(values, required=False)
        mode = values.get('mode', 'http')
        if mode not in ('http', 'https', 'both'):
            raise ValidationError(message('badMode', value=mode))
        http_port = self._port(values, 'http_port', 'serverHttpPort') if mode != 'https' else 0
        https_port = self._port(values, 'https_port', 'serverHttpsPort') if mode != 'http' else 0
        if http_port and http_port == https_port:
            raise ValidationError(message('serverPortsEqual'))
        certificate = key = ''
        if https_port:
            certificate, key = self._certificate()
        captures = str(self._capture_dir) if self._flag(values, 'share') else ''
        argv = self._commands.web_server(
            str(self._folder('web')), http_port, https_port, address, captures, certificate, key)
        if captures and self._settings_path:
            argv += ['--journal-settings', str(self._settings_path)]
        return _Plan(argv)

    def _certificate(self) -> tuple[str, str]:
        folder = self._state('web')
        certificate, key = folder / 'cert.pem', folder / 'key.pem'
        if self._posix and not (certificate.exists() and key.exists()):
            result = self._runner.run(self._commands.tls_certificate(str(certificate), str(key)))
            if not result.ok:
                raise CommandFailedError(message('serverPrepare', detail=_first_line(result.text)), result)
        return str(certificate), str(key)

    def _dns(self, values: Mapping[str, str]) -> _Plan:
        _name, address, _prefix = self._interface(values, required=True)
        name = validation.dns_name(values.get('name', ''))
        answer_text = (values.get('answer') or '').strip()
        answer = validation.ipv4_address(answer_text, message('serverAnswer')) if answer_text else address
        upstream_text = (values.get('upstream') or '').strip()
        upstream = validation.ipv4_address(upstream_text, message('serverUpstream')) if upstream_text else ''
        pid = self._state('dns') / 'dnsmasq.pid'
        return _Plan(self._commands.dns_server(
            address, self._port(values), name, answer, upstream, str(pid)))

    def _dhcp(self, values: Mapping[str, str]) -> _Plan:
        name, address, prefix = self._interface(values, required=True)
        route = self._runner.run(self._commands.interface_gateway(name))
        if route.ok and parse_default_gateway(route.stdout):
            raise ValidationError(message('dhcpUplink', interface=name))
        network = ipaddress.IPv4Network(f'{address}/{prefix}', strict=False)
        if network.prefixlen > 29:
            raise ValidationError(message('dhcpSmallNet', interface=name))
        first, last = _dhcp_range(network, address, values)
        gateway = _optional_ip(values.get('gateway'), message('fieldGateway'), address)
        dns = _optional_ip(values.get('dns'), 'DNS', address)
        hours = validation.integer_between(values.get('hours', ''), 1, 168, message('serverLease'))
        folder = self._state('dhcp')
        return _Plan(self._commands.dhcp_server(
            name, first, last, str(network.netmask), hours, gateway, dns,
            str(folder / 'dnsmasq.leases'), str(folder / 'dnsmasq.pid')))


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
    first = int(ipaddress.IPv4Address(validation.ipv4_address(first_text, message('serverFrom')))) if first_text else start
    last = int(ipaddress.IPv4Address(validation.ipv4_address(last_text, message('serverTo')))) if last_text else end
    if first_text and not last_text:
        last = min(first + 50, top - 1)
    if last_text and not first_text:
        first = max(base + 1, last - 50)
    inside = base < first <= last < top
    if not inside or first <= own <= last:
        raise ValidationError(message('dhcpRange'))
    return str(ipaddress.IPv4Address(first)), str(ipaddress.IPv4Address(last))
