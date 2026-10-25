from __future__ import annotations

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError
from mulita.core.models import WifiLink, WifiNetwork
from mulita.core.parsers import build_wifi_link, parse_wifi_device, parse_wifi_list
from mulita.core.ports import CommandRunner


class WifiService:
    """Busca redes y se conecta con NetworkManager."""

    def __init__(self, runner: CommandRunner, commands: CommandFactory):
        self._runner = runner
        self._commands = commands

    def interface(self) -> str | None:
        result = self._checked(self._commands.wifi_devices(), 'No se pudo leer el Wi-Fi')
        return parse_wifi_device(result.stdout)

    def scan(self) -> tuple[str | None, tuple[WifiNetwork, ...], WifiLink]:
        device = self.interface()
        if not device:
            return None, (), WifiLink()
        self._runner.run(self._commands.wifi_rescan(device))
        listed = self._checked(self._commands.wifi_list(device), 'No se pudieron buscar redes')
        networks = tuple(parse_wifi_list(listed.stdout))
        return device, networks, self._link(device, networks)

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
