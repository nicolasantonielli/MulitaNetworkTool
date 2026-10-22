from __future__ import annotations

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError
from mulita.core.models import Calibration, ClimateReading, SpeedTestResult
from mulita.core.parsers import parse_speed_test
from mulita.core.ports import ClimateSensor, CommandRunner


class WakeOnLanService:

    def __init__(self, runner: CommandRunner, commands: CommandFactory):
        self._runner = runner
        self._commands = commands

    def wake(self, mac: str) -> str:
        return self._runner.run(self._commands.wake_on_lan(validation.mac_address(mac))).text


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
