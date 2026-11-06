"""Comandos de red: Ethernet, VLAN, enlaces, puentes, espejo de trafico y rutas."""
from __future__ import annotations

from mulita.core.command_base import Argv, CommandBase


class NetworkCommands(CommandBase):

    def interfaces(self) -> Argv:
        return [self._bin.ip, '-j', 'addr']

    def ethernet_connection(self, interface: str) -> Argv:
        return [self._bin.nmcli, '-g', 'GENERAL.CONNECTION', 'device', 'show', interface]

    def ethernet_ipv4(self, connection: str) -> Argv:
        return [self._bin.nmcli, '-g', 'ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns',
                'connection', 'show', connection]

    def ethernet_lease(self, interface: str) -> Argv:
        return [self._bin.nmcli, '-t', '-f', 'IP4.ADDRESS,IP4.GATEWAY,IP4.DNS',
                'device', 'show', interface]

    def interface_ipv4(self, interface: str) -> Argv:
        return [self._bin.ip, '-j', 'addr', 'show', 'dev', interface]

    def interface_gateway(self, interface: str) -> Argv:
        return [self._bin.ip, '-j', 'route', 'show', 'default', 'dev', interface]

    def add_ethernet_connection(self, name: str, interface: str) -> Argv:
        return [self._bin.nmcli, 'connection', 'add', 'type', 'ethernet',
                'ifname', interface, 'con-name', name, 'ipv4.method', 'auto']

    def set_dhcp(self, connection: str) -> Argv:
        return [self._bin.nmcli, 'connection', 'modify', connection,
                'ipv4.method', 'auto',
                'ipv4.addresses', '', 'ipv4.gateway', '', 'ipv4.dns', '']

    def set_static(self, connection: str, cidr: str, gateway: str, dns: str) -> Argv:
        return [self._bin.nmcli, 'connection', 'modify', connection,
                'ipv4.method', 'manual',
                'ipv4.addresses', cidr, 'ipv4.gateway', gateway, 'ipv4.dns', dns]

    def activate_connection(self, connection: str) -> Argv:
        return [self._bin.nmcli, 'connection', 'up', connection]

    def vlan_info(self, name: str) -> Argv:
        return [self._bin.nmcli, '-g', 'vlan.id', 'connection', 'show', 'id', name]

    def add_vlan(self, name: str, parent: str, vlan_id: int) -> Argv:
        return [self._bin.nmcli, 'connection', 'add', 'type', 'vlan', 'con-name', name,
                'ifname', f'{parent}.{vlan_id}', 'dev', parent, 'id', str(vlan_id)]

    def modify_vlan(self, name: str, parent: str, vlan_id: int) -> Argv:
        return [self._bin.nmcli, 'connection', 'modify', name, 'vlan.id', str(vlan_id),
                'vlan.parent', parent, 'connection.interface-name', f'{parent}.{vlan_id}']

    def delete_connection(self, name: str) -> Argv:
        return [self._bin.nmcli, 'connection', 'delete', 'id', name]

    def detailed_links(self) -> Argv:
        return [self._bin.ip, '-j', '-d', 'link', 'show']

    def delete_link(self, interface: str) -> Argv:
        return [self._bin.ip, 'link', 'delete', 'dev', interface]

    def link_add_bridge(self, name: str) -> Argv:
        return [self._bin.ip, 'link', 'add', 'name', name, 'type', 'bridge']

    def link_prepare_bridge(self, name: str) -> Argv:
        return [self._bin.ip, 'link', 'set', 'dev', name, 'type', 'bridge',
                'stp_state', '0', 'forward_delay', '0']

    def link_up(self, name: str) -> Argv:
        return [self._bin.ip, 'link', 'set', 'dev', name, 'up']

    def link_master(self, interface: str, bridge: str) -> Argv:
        return [self._bin.ip, 'link', 'set', 'dev', interface, 'master', bridge]

    def link_nomaster(self, interface: str) -> Argv:
        return [self._bin.ip, 'link', 'set', 'dev', interface, 'nomaster']

    def link_promisc(self, interface: str, enabled: bool) -> Argv:
        return [self._bin.ip, 'link', 'set', 'dev', interface, 'promisc', 'on' if enabled else 'off']

    def link_delete(self, name: str) -> Argv:
        return [self._bin.ip, 'link', 'del', 'dev', name]

    def ingress_add(self, interface: str) -> Argv:
        return [self._bin.tc, 'qdisc', 'add', 'dev', interface, 'ingress']

    def ingress_delete(self, interface: str) -> Argv:
        return [self._bin.tc, 'qdisc', 'del', 'dev', interface, 'ingress']

    def mirror_traffic(self, interface: str, mirror: str) -> Argv:
        return [self._bin.tc, 'filter', 'add', 'dev', interface, 'parent', 'ffff:',
                'protocol', 'all', 'u32', 'match', 'u32', '0', '0',
                'action', 'mirred', 'egress', 'mirror', 'dev', mirror]

    def rule_add_from(self, source: str, table: str) -> Argv:
        return [self._bin.ip, 'rule', 'add', 'from', source, 'lookup', table, 'priority', '50']

    def rule_del_from(self, source: str, table: str) -> Argv:
        return [self._bin.ip, 'rule', 'del', 'from', source, 'lookup', table, 'priority', '50']

    def route_replace_default(self, gateway: str, interface: str, table: str) -> Argv:
        return [self._bin.ip, 'route', 'replace', 'default', 'via', gateway,
                'dev', interface, 'onlink', 'table', table]

    def route_flush_table(self, table: str) -> Argv:
        return [self._bin.ip, 'route', 'flush', 'table', table]
