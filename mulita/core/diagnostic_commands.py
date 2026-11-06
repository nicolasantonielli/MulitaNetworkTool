"""Comandos de diagnostico: captura, trazas, ping, escaneos y consultas externas."""
from __future__ import annotations

from pathlib import PurePosixPath

from mulita.core.command_base import Argv, CommandBase
from mulita.core.models import CaptureRequest, PingRequest


class DiagnosticCommands(CommandBase):

    def capture(self, request: CaptureRequest, directory: PurePosixPath) -> Argv:
        return [self._bin.tcpdump,
                '-Q', request.direction.value,
                '-i', request.interface,
                '-w', str(directory / request.filename)]

    def trace(self, target: str, cycles: int) -> Argv:
        return [self._bin.mtr, target, '-n', '-r', '--csv', '-c', str(cycles)]

    def ping(self, request: PingRequest) -> Argv:
        argv = [self._bin.ping, request.target, '-n']
        if not request.continuous:
            argv += ['-c', str(request.count)]
        argv += ['-i', f'{request.interval:.2f}', '-s', str(request.payload_bytes)]
        return argv

    def port_scan(self, arguments: list[str]) -> Argv:
        return [self._bin.nmap, *arguments]

    def nmap(self, arguments: list[str]) -> Argv:
        return [self._bin.nmap, *arguments]

    def discovery(self, interface: str = '', network: str = '') -> Argv:
        # -d no lee ~/.netdiscover. -L deja la salida parseable y sigue
        # escuchando. Sin -f recorre toda la red, no solo .1 .100 y .254.
        argv = [self._bin.netdiscover, '-L', '-N', '-d']
        if interface:
            argv += ['-i', interface]
        if network:
            argv += ['-r', network]
        return argv

    def tls_scan(self, target: str, flags: list[str], report: str) -> Argv:
        # --warnings batch evita las preguntas, --color 0 deja texto plano y
        # --ip one prueba una sola direccion aunque el nombre tenga varias.
        return [self._bin.testssl, '--quiet', '--color', '0', '--warnings', 'batch',
                '--connect-timeout', '10', '--openssl-timeout', '10', '--ip', 'one',
                '--jsonfile', report, *flags, target]

    def wake_on_lan(self, mac: str) -> Argv:
        return [self._bin.wakeonlan, mac]

    def speed_test(self, source: str = '') -> Argv:
        argv = [self._bin.speedtest, '--json', '--timeout', '25']
        if source:
            argv += ['--source', source]
        return argv

    def public_ip(self, url: str, timeout: int) -> Argv:
        return [self._bin.curl, '-s', '--max-time', str(timeout), url]

    def mac_vendor(self, url: str, mac: str, timeout: int) -> Argv:
        # El codigo HTTP va al final de la salida. 404 y 429 no son un fallo de curl.
        return [self._bin.curl, '-sS', '--max-time', str(timeout),
                '-w', '\n%{http_code}', f'{url.rstrip("/")}/{mac}']
