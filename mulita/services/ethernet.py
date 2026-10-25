from __future__ import annotations

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError
from mulita.core.models import AddressMode, EthernetConfig
from mulita.core.parsers import parse_connection_name, parse_nmcli_ipv4
from mulita.core.ports import CommandRunner


class EthernetService:
    """Dirección de la ethernet interna, por DHCP o fija, vía NetworkManager."""

    def __init__(self, runner: CommandRunner, commands: CommandFactory,
                 interface: str, connection_name: str):
        self._runner = runner
        self._commands = commands
        self._interface = interface
        self._connection_name = connection_name

    @property
    def interface(self) -> str:
        return self._interface

    def read(self) -> EthernetConfig:
        name = self._connection()
        if name is None:
            return EthernetConfig()
        shown = self._checked(self._commands.ethernet_ipv4(name), 'No se pudo leer la ethernet interna')
        return parse_nmcli_ipv4(shown.stdout)

    def apply_dhcp(self) -> EthernetConfig:
        name = self._ensure()
        self._checked(self._commands.set_dhcp(name), 'No se pudo activar DHCP')
        self._checked(self._commands.activate_connection(name), 'No se pudo aplicar DHCP')
        return EthernetConfig(AddressMode.DHCP)

    def apply_static(self, address: str, netmask: str, gateway: str = '', dns: str = '') -> EthernetConfig:
        config = validation.static_ethernet(address, netmask, gateway, dns)
        name = self._ensure()
        cidr = f'{config.address}/{config.prefix}'
        self._checked(self._commands.set_static(name, cidr, config.gateway, config.dns),
                      'No se pudo guardar la direccion estatica')
        self._checked(self._commands.activate_connection(name), 'No se pudo aplicar la direccion estatica')
        return config

    def _connection(self) -> str | None:
        result = self._checked(self._commands.ethernet_connection(self._interface),
                               'No se pudo leer la ethernet interna')
        return parse_connection_name(result.stdout)

    def _ensure(self) -> str:
        name = self._connection()
        if name:
            return name
        self._checked(self._commands.add_ethernet_connection(self._connection_name, self._interface),
                      'No se pudo crear la conexion')
        return self._connection_name

    def _checked(self, argv: list[str], message: str):
        result = self._runner.run(argv)
        if not result.ok:
            raise CommandFailedError(f'{message}: {result.text}', result)
        return result
