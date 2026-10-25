from __future__ import annotations

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError
from mulita.core.models import WifiNetwork
from mulita.core.parsers import parse_wifi_device, parse_wifi_list
from mulita.core.ports import CommandRunner


class WifiService:
    """Busca redes y se conecta con NetworkManager."""

    def __init__(self, runner: CommandRunner, commands: CommandFactory):
        self._runner = runner
        self._commands = commands

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

    def connect(self, ssid: str, password: str, secure: bool) -> str:
        name = validation.wifi_ssid(ssid)
        secret = validation.wifi_password(password, required=secure)
        device = self.interface()
        if not device:
            raise CommandFailedError('No hay una interfaz Wi-Fi')
        if secret:
            self._runner.run(self._commands.wifi_delete(name))
        failed = self._runner.run(self._commands.wifi_connect(device, name, secret))
        if failed.ok:
            return name
        if secret:
            repaired = self._runner.run(self._commands.wifi_set_psk(name, secret))
            if repaired.ok:
                self._checked(self._commands.wifi_up(name, device), f'No se pudo conectar a {name}')
                return name
        raise CommandFailedError(f'No se pudo conectar a {name}: {failed.text}', failed)

    def _checked(self, argv: list[str], message: str):
        result = self._runner.run(argv)
        if not result.ok:
            raise CommandFailedError(f'{message}: {result.text}', result)
        return result
