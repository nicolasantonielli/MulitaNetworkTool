"""Comandos de servidores y de las cuentas que necesitan."""
from __future__ import annotations

from pathlib import PurePosixPath
from mulita.config import Binaries

Argv = list[str]


class ServerCommands:
    def __init__(self, binaries: Binaries, server_programs: PurePosixPath | None = None):
        self._bin = binaries
        self._server_programs = server_programs

    def _script(self, name: str) -> Argv:
        """Servidores propios (TFTP, web, NTP): scripts de la biblioteca estandar, sin salida diferida."""
        if self._server_programs is None:
            raise ValueError('Server program directory must be supplied by the composition root')
        return [self._bin.python, '-u', str(self._server_programs / f'{name}.py')]

    def _dnsmasq_base(self, pid_file: str) -> Argv:
        # --conf-file=/dev/null ignora /etc/dnsmasq.conf. --user=root evita problemas de permisos
        # sobre la carpeta de estado. Cada instancia usa su propio pid para no pisar la del sistema.
        return [self._bin.dnsmasq, '--keep-in-foreground', '--conf-file=/dev/null',
                f'--pid-file={pid_file}', '--user=root', '--no-hosts', '--log-facility=-']

    def iperf_server(self, port: int, bind: str = '', one_off: bool = False) -> Argv:
        argv = [self._bin.iperf3, '-s', '-p', str(port), '--forceflush']
        if bind:
            argv += ['-B', bind]
        if one_off:
            argv.append('-1')
        return argv

    def tftp_server(self, root: str, port: int, bind: str = '', writable: bool = True) -> Argv:
        argv = self._script('tftp') + ['--root', root, '--port', str(port)]
        if bind:
            argv += ['--bind', bind]
        if writable:
            argv.append('--writable')
        return argv

    def web_server(self, root: str, http_port: int, https_port: int, bind: str = '',
                   captures: str = '', cert: str = '', key: str = '') -> Argv:
        """Un puerto en cero deja ese protocolo apagado."""
        argv = self._script('web') + ['--root', root,
                                      '--http-port', str(http_port), '--https-port', str(https_port)]
        if bind:
            argv += ['--bind', bind]
        if captures:
            argv += ['--captures', captures]
        if https_port:
            argv += ['--cert', cert, '--key', key]
        return argv

    def ntp_server(self, port: int, stratum: int, bind: str = '') -> Argv:
        argv = self._script('ntp') + ['--port', str(port), '--stratum', str(stratum)]
        if bind:
            argv += ['--bind', bind]
        return argv

    def dns_server(self, address: str, port: int, name: str, answer: str,
                   upstream: str, pid_file: str) -> Argv:
        # --cache-size=0 deja pasar cada consulta, asi el registro muestra todo lo que pide el equipo.
        argv = self._dnsmasq_base(pid_file) + [
            f'--port={port}', '--no-resolv', '--cache-size=0',
            '--log-queries', f'--address=/{name}/{answer}']
        if address:
            argv += [f'--listen-address={address}', '--bind-interfaces']
        if upstream:
            argv.append(f'--server={upstream}')
        return argv

    def dhcp_server(self, interface: str, first: str, last: str, netmask: str, hours: int,
                    gateway: str, dns: str, leases: str, pid_file: str) -> Argv:
        # --port=0 apaga el DNS de esta instancia. --bind-interfaces la limita a un solo puerto.
        return self._dnsmasq_base(pid_file) + [
            '--port=0', '--no-resolv', '--bind-interfaces', f'--interface={interface}',
            f'--dhcp-range={first},{last},{netmask},{hours}h',
            f'--dhcp-option=option:router,{gateway}',
            f'--dhcp-option=option:dns-server,{dns}',
            f'--dhcp-leasefile={leases}', '--dhcp-authoritative', '--log-dhcp']

    def sftp_server(self, config: str) -> Argv:
        return [self._bin.sshd, '-D', '-e', '-f', config]

    def ssh_host_key(self, path: str) -> Argv:
        return [self._bin.ssh_keygen, '-q', '-t', 'ed25519', '-N', '', '-f', path]

    def tls_certificate(self, certificate: str, key: str) -> Argv:
        return [self._bin.openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256',
                '-days', '3650', '-subj', '/CN=mulita', '-keyout', key, '-out', certificate]

    def user_entry(self, name: str) -> Argv:
        return [self._bin.getent, 'passwd', name]

    def user_add(self, name: str, comment: str) -> Argv:
        return [self._bin.useradd, '--no-create-home', '--home-dir', '/',
                '--shell', '/usr/sbin/nologin', '--comment', comment, name]

    def user_delete(self, name: str) -> Argv:
        return [self._bin.userdel, '--force', name]

    def set_password(self) -> Argv:
        """Lee `usuario:clave` de la entrada estandar."""
        return [self._bin.chpasswd]

    def change_owner(self, owner: str, path: str, recursive: bool = False) -> Argv:
        argv = [self._bin.chown]
        if recursive:
            argv.append('-R')
        return argv + [owner, path]

