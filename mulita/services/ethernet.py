from __future__ import annotations

from mulita.core.events import EventSource
from mulita.services.operation_events import operation

import json

from mulita.core import validation
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.messages import message
from mulita.core.models import AddressMode, EthernetConfig
from mulita.core.parsers import (parse_connection_name, parse_default_gateway,
                                parse_interface_ipv4, parse_nmcli_device_ipv4,
                                parse_nmcli_ipv4)
from mulita.core.ports import CommandRunner


class EthernetService(EventSource):
    """Dirección de la ethernet interna, por DHCP o fija, vía NetworkManager."""

    def __init__(self, runner: CommandRunner, commands: CommandFactory,
                 interface: str, connection_name: str):
        self._runner = runner
        self._commands = commands
        self._interface = interface
        self._connection_name = connection_name
        self._vlan_id = 0

    @property
    def vlan_id(self) -> int:
        return self._vlan_id

    @property
    def _vlan_name(self) -> str:
        return self._connection_name + '-vlan'

    def _stored_vlan(self) -> int:
        result = self._runner.run(self._commands.vlan_info(self._vlan_name))
        if result.returncode == 10:
            return 0
        if not result.ok:
            raise CommandFailedError(message('vlanFailed'), result)
        try:
            value = int(result.stdout.strip())
        except ValueError as exc:
            raise ValidationError(message('vlanFailed')) from exc
        if not 1 <= value <= 4094:
            raise ValidationError(message('vlanFailed'))
        return value

    def read_with_vlan(self) -> EthernetConfig:
        self._vlan_id = self._stored_vlan()
        return self.read()

    def _remove_tagged_interfaces(self) -> None:
        result = self._checked(self._commands.detailed_links(), message('vlanFailed'))
        try:
            links = json.loads(result.stdout)
            if not isinstance(links, list) or any(not isinstance(link, dict) for link in links):
                raise ValueError('Invalid link list')
        except (ValueError, TypeError) as exc:
            raise CommandFailedError(message('vlanFailed')) from exc
        parent_index = next((link.get('ifindex') for link in links
                             if link.get('ifname') == self._interface), None)
        for link in links:
            if (link.get('linkinfo') or {}).get('info_kind') != 'vlan':
                continue
            if not ((parent_index is not None and link.get('link_index') == parent_index)
                    or link.get('link') == self._interface):
                continue
            name = link.get('ifname')
            if not isinstance(name, str) or not name or name == self._interface:
                raise CommandFailedError(message('vlanFailed'))
            self._checked(self._commands.delete_link(name), message('vlanFailed'))

    @operation('vlan', 'enabled', 'vlan', context=lambda self: {'interface': self.interface})
    def apply_with_vlan(self, mode: str, address: str, netmask: str, gateway: str,
                        dns: str, enabled: bool, vlan: str) -> EthernetConfig:
        if mode not in ('dhcp', 'static'):
            raise ValidationError(message('invalidMode', mode=mode))
        config = validation.static_ethernet(address, netmask, gateway, dns) if mode == 'static' else None
        try:
            tag = int(vlan) if enabled else 0
        except ValueError as exc:
            raise ValidationError(message('vlanInvalid')) from exc
        if enabled and not 1 <= tag <= 4094:
            raise ValidationError(message('vlanInvalid'))
        existing = self._stored_vlan()
        if enabled:
            command = (self._commands.modify_vlan if existing else self._commands.add_vlan)
            self._checked(command(self._vlan_name, self._interface, tag), message('vlanFailed'))
            self._vlan_id = tag
        else:
            if existing:
                self._checked(self._commands.delete_connection(self._vlan_name), message('vlanFailed'))
            self._remove_tagged_interfaces()
            self._vlan_id = 0
        if config:
            return self.apply_static(address, netmask, gateway, dns)
        return self.apply_dhcp()

    @property
    def interface(self) -> str:
        return f'{self._interface}.{self._vlan_id}' if self._vlan_id else self._interface

    def read(self) -> EthernetConfig:
        name = self._connection()
        if name is None:
            return self.lease()
        shown = self._checked(self._commands.ethernet_ipv4(name), 'No se pudo leer la ethernet interna')
        config = parse_nmcli_ipv4(shown.stdout)
        if config.mode is AddressMode.DHCP:
            return self.lease()
        return config

    def lease(self) -> EthernetConfig:
        """La IP y la máscara salen de la interfaz. nmcli a veces no trae esos campos y sí el DNS."""
        reported = parse_nmcli_device_ipv4(self._checked(
            self._commands.ethernet_lease(self.interface), 'No se pudo leer la direccion DHCP').stdout)
        address, prefix = parse_interface_ipv4(self._checked(
            self._commands.interface_ipv4(self.interface), 'No se pudo leer la IP de la interfaz').stdout)
        gateway = parse_default_gateway(self._checked(
            self._commands.interface_gateway(self.interface), 'No se pudo leer la puerta de enlace').stdout)
        if not address:
            address, prefix = reported.address, reported.prefix
        if not gateway:
            gateway = reported.gateway
        return EthernetConfig(AddressMode.DHCP, address, prefix, gateway, reported.dns)

    @operation('ipv4_ethernet', context=lambda self: {'interface': self.interface})
    def apply_dhcp(self) -> EthernetConfig:
        name = self._ensure()
        self._checked(self._commands.set_dhcp(name), 'No se pudo activar DHCP')
        self._checked(self._commands.activate_connection(name), 'No se pudo aplicar DHCP')
        return self.lease()

    @operation('ipv4_ethernet', context=lambda self: {'interface': self.interface})
    def apply_static(self, address: str, netmask: str, gateway: str = '', dns: str = '') -> EthernetConfig:
        config = validation.static_ethernet(address, netmask, gateway, dns)
        name = self._ensure()
        cidr = f'{config.address}/{config.prefix}'
        self._checked(self._commands.set_static(name, cidr, config.gateway, config.dns),
                      'No se pudo guardar la direccion estatica')
        self._checked(self._commands.activate_connection(name), 'No se pudo aplicar la direccion estatica')
        return config

    def _connection(self) -> str | None:
        if self._vlan_id:
            return self._vlan_name
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

    def _checked(self, argv: list[str], error_message: str):
        result = self._runner.run(argv)
        if not result.ok:
            raise CommandFailedError(message('commandFailure', message=error_message, detail=result.text), result)
        return result
