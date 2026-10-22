"""Traduce pedidos del negocio a lineas de comando. Siempre listas, nunca shell."""
from __future__ import annotations

from pathlib import PurePosixPath

from mulita.config import Binaries
from mulita.core.models import CaptureRequest, PingRequest

Argv = list[str]


class CommandFactory:

    def __init__(self, binaries: Binaries):
        self._bin = binaries

    def interfaces(self) -> Argv:
        return [self._bin.ip, '-j', 'addr']

    def capture(self, request: CaptureRequest, directory: PurePosixPath) -> Argv:
        return [self._bin.tcpdump,
                '-Q', request.direction.value,
                '-i', request.interface,
                '-w', str(directory / request.filename)]

    def trace(self, target: str, cycles: int) -> Argv:
        return [self._bin.mtr, target, '-n', '-r', '-c', str(cycles)]

    def ping(self, request: PingRequest) -> Argv:
        argv = [self._bin.ping, request.target, '-n']
        if not request.continuous:
            argv += ['-c', str(request.count)]
        argv += ['-i', f'{request.interval:.2f}', '-s', str(request.payload_bytes)]
        return argv

    def port_scan(self, arguments: list[str]) -> Argv:
        return [self._bin.nmap, *arguments]

    def discovery(self) -> Argv:
        return [self._bin.netdiscover, '-f', '-P']

    def wake_on_lan(self, mac: str) -> Argv:
        return [self._bin.wakeonlan, mac]

    def speed_test(self) -> Argv:
        return [self._bin.speedtest, '--json']

    def public_ip(self, url: str, timeout: int) -> Argv:
        return [self._bin.curl, '-s', '--max-time', str(timeout), url]

    def keyboard(self) -> Argv:
        return [self._bin.onboard]

    def hide_keyboard(self) -> Argv:
        return [self._bin.killall, 'onboard']

    def update(self, repository_dir: str) -> Argv:
        return [self._bin.git, '-C', repository_dir, 'pull']

    def reset(self, script: str) -> Argv:
        return [self._bin.bash, script]

    def poweroff(self) -> Argv:
        return [self._bin.poweroff]
