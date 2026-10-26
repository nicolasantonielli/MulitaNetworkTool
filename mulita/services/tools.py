from __future__ import annotations

import re
import time
from dataclasses import dataclass

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError
from mulita.presentation.i18n import tr
from mulita.core.models import Calibration, ClimateReading, SpeedTestResult
from mulita.core.parsers import parse_mac_vendor, parse_speed_test
from mulita.core.ports import ClimateSensor, CommandRunner


_WAKE_TARGET = re.compile(r'(\d+\.\d+\.\d+\.\d+):(\d+)')


@dataclass(frozen=True)
class MagicPacket:
    mac: str
    target: str
    port: str


class WakeOnLanService:

    def __init__(self, runner: CommandRunner, commands: CommandFactory):
        self._runner = runner
        self._commands = commands

    def wake(self, mac: str) -> MagicPacket:
        normalized = validation.mac_address(mac)
        result = self._runner.run(self._commands.wake_on_lan(normalized))
        if not result.ok:
            detail = (result.text or '').strip()
            raise CommandFailedError(detail or tr('wolFailed'), result)
        found = _WAKE_TARGET.search(result.stdout or '')
        target, port = found.groups() if found else ('255.255.255.255', '9')
        return MagicPacket(normalized.upper(), target, port)


class ClimateService:

    def __init__(self, sensor: ClimateSensor, calibration: Calibration):
        self._sensor = sensor
        self._calibration = calibration

    def read(self) -> ClimateReading | None:
        reading = self._sensor.read()
        return self._calibration.apply(reading) if reading else None


class SpeedTestService:

    def __init__(self, runner: CommandRunner, commands: CommandFactory):
        self._runner = runner
        self._commands = commands

    def measure(self) -> SpeedTestResult:
        result = self._runner.run(self._commands.speed_test())
        if not result.ok:
            raise CommandFailedError(f'Fallo el test de velocidad: {result.text}', result)
        return parse_speed_test(result.stdout)


class PublicIpService:

    def __init__(self, runner: CommandRunner, commands: CommandFactory, url: str, timeout: int):
        self._runner = runner
        self._commands = commands
        self._url = url
        self._timeout = timeout

    def lookup(self) -> str:
        result = self._runner.run(self._commands.public_ip(self._url, self._timeout))
        address = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ''
        if not result.ok or not address:
            raise CommandFailedError('No se pudo obtener la IP publica', result)
        return address


class MacVendorService:
    """Fabricante de una MAC via api.macvendors.com. Una consulta por segundo."""

    def __init__(self, runner: CommandRunner, commands: CommandFactory, url: str, timeout: int):
        self._runner = runner
        self._commands = commands
        self._url = url
        self._timeout = timeout
        self._next_at = 0.0

    def lookup(self, mac: str) -> str:
        text = validation.mac_address(mac).replace('-', ':').upper()
        self._pace()
        result = self._runner.run(self._commands.mac_vendor(self._url, text, self._timeout))
        if not result.ok:
            raise CommandFailedError('No se pudo consultar el fabricante', result)
        return parse_mac_vendor(result.stdout)

    def _pace(self) -> None:
        wait = self._next_at - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._next_at = time.monotonic() + 1
