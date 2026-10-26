from __future__ import annotations

import csv
import ipaddress
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.presentation.i18n import tr
from mulita.core.models import Calibration, ClimateReading, SpeedTestResult
from mulita.core.parsers import (parse_interfaces, parse_mac_vendor,
                                parse_public_address, parse_speed_test)
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

    def measure(self, interface: str = '') -> SpeedTestResult:
        source = self._source_address(interface) if (interface or '').strip() else ''
        result = self._runner.run(self._commands.speed_test(source))
        if not result.ok:
            raise CommandFailedError(f'Fallo el test de velocidad: {result.text}', result)
        return parse_speed_test(result.stdout)

    def _source_address(self, interface: str) -> str:
        name = (interface or '').strip()
        listed = self._runner.run(self._commands.interfaces())
        if not listed.ok:
            raise CommandFailedError(tr('speedNoIface'), listed)
        for item in parse_interfaces(listed.stdout):
            if item.name != name:
                continue
            for address in item.addresses:
                try:
                    ip = ipaddress.ip_address(address)
                except ValueError:
                    continue
                if ip.version == 4 and not ip.is_loopback and not ip.is_link_local:
                    return address
        raise ValidationError(tr('speedNoAddress', interface=name))


class PublicIpService:

    def __init__(self, runner: CommandRunner, commands: CommandFactory, url: str, timeout: int,
                 directory: PurePosixPath | Path = PurePosixPath('/root/capturas/internet')):
        self._runner = runner
        self._commands = commands
        self._url = url
        self._timeout = timeout
        self._directory = Path(directory)

    def lookup(self) -> PublicAddress:
        result = self._runner.run(self._commands.public_ip(self._url, self._timeout))
        if not result.ok or not (result.stdout or '').strip():
            raise CommandFailedError(tr('pubFail'), result)
        return parse_public_address(result.stdout)

    def save(self, info: PublicAddress, moment: datetime | None = None) -> str:
        if not info.ip:
            raise ValidationError(tr('noPublic'))
        when = moment or datetime.now()
        name = f"publicIP-{when.strftime('%Y%m%d-%H%M%S')}.csv"
        self._ensure_directory()
        path = self._directory / name
        if path.parent.resolve() != self._directory.resolve():
            raise ValidationError(tr('badStoredName'))
        if path.exists():
            raise ValidationError(tr('nameExists'))
        facts = info.facts()
        try:
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle, lineterminator='\n')
                writer.writerow([label for label, _value in facts])
                writer.writerow([value for _label, value in facts])
        except OSError as exc:
            raise CommandFailedError(tr('savePublicFailed')) from exc
        if hasattr(os, 'sync'):
            os.sync()
        return name

    def _ensure_directory(self) -> None:
        if os.name != 'posix':
            return
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(tr('publicFolder')) from exc


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
