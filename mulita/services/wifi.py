from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path, PurePosixPath

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.models import WifiLink, WifiNetwork
from mulita.core.parsers import build_wifi_link, parse_wifi_device, parse_wifi_list
from mulita.core.ports import CommandRunner
from mulita.presentation.i18n import tr


class WifiService:
    """Busca redes y se conecta con NetworkManager."""

    def __init__(self, runner: CommandRunner, commands: CommandFactory,
                 directory: PurePosixPath | Path = PurePosixPath('/root/capturas/wifi')):
        self._runner = runner
        self._commands = commands
        self._directory = Path(directory)

    def interface(self) -> str | None:
        result = self._checked(self._commands.wifi_devices(), 'No se pudo leer el Wi-Fi')
        return parse_wifi_device(result.stdout)

    def scan(self) -> tuple[str | None, tuple[WifiNetwork, ...]]:
        device = self.interface()
        if not device:
            return None, ()
        self._runner.run(self._commands.wifi_rescan(device))
        listed = self._checked(self._commands.wifi_list(device), 'No se pudieron buscar redes')
        return device, tuple(parse_wifi_list(listed.stdout))

    def save(self, link: WifiLink, moment: datetime | None = None) -> str:
        facts = link.facts()
        if not facts:
            raise ValidationError(tr('noWifiSave'))
        when = moment or datetime.now()
        name = f"wifi-info-{when.strftime('%Y%m%d-%H%M%S')}.csv"
        self._ensure_directory()
        path = self._directory / name
        if path.parent.resolve() != self._directory.resolve():
            raise ValidationError(tr('badStoredName'))
        if path.exists():
            raise ValidationError(tr('nameExists'))
        try:
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle, lineterminator='\n')
                for label, value in facts:
                    writer.writerow([label, value])
        except OSError as exc:
            raise CommandFailedError(tr('saveWifiFailed')) from exc
        if hasattr(os, 'sync'):
            os.sync()
        return name

    def _ensure_directory(self) -> None:
        if os.name != 'posix':
            return
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(tr('wifiFolder')) from exc

    def status(self) -> WifiLink:
        """Dirección y radio del enlace, sin disparar un escaneo de redes."""
        device = self.interface()
        if not device:
            return WifiLink()
        return self._link(device, ())

    def _link(self, device: str, networks: tuple[WifiNetwork, ...]) -> WifiLink:
        commands = self._commands
        return build_wifi_link(
            device,
            self._text(commands.interface_ipv4(device)),
            self._text(commands.interface_gateway(device)),
            self._text(commands.ethernet_lease(device)),
            self._text(commands.wifi_details(device)),
            self._text(commands.wifi_link(device)),
            self._text(commands.wifi_info(device)),
            self._text(commands.wifi_station(device)),
            self._text(commands.wifi_survey(device)),
            networks)

    def _text(self, argv: list[str]) -> str:
        result = self._runner.run(argv)
        return result.stdout if result.ok else ''

    def connect(self, ssid: str, password: str, secure: bool) -> str:
        name = validation.wifi_ssid(ssid)
        secret = validation.wifi_password(password, required=secure)
        device = self.interface()
        if not device:
            raise CommandFailedError('No hay una interfaz Wi-Fi')
        if not secret:
            self._checked(self._commands.wifi_connect(device, name, ''),
                          f'No se pudo conectar a {name}')
            return name
        self._runner.run(self._commands.wifi_delete(name))
        added = self._runner.run(self._commands.wifi_add_secured(device, name, secret))
        if not added.ok:
            self._checked(self._commands.wifi_set_psk(name, secret),
                          f'No se pudo guardar la clave de {name}')
        self._checked(self._commands.wifi_up(name, device), f'No se pudo conectar a {name}')
        return name

    def _checked(self, argv: list[str], message: str):
        result = self._runner.run(argv)
        if not result.ok:
            raise CommandFailedError(f'{message}: {result.text}', result)
        return result
