"""Comandos de Wi-Fi: nmcli e iw."""
from __future__ import annotations

from mulita.core.command_base import Argv
from mulita.core.network_commands import NetworkCommands


class WifiCommands(NetworkCommands):

    def wifi_devices(self) -> Argv:
        return [self._bin.nmcli, '-t', '-f', 'DEVICE,TYPE', 'device', 'status']

    def wifi_rescan(self, interface: str) -> Argv:
        return [self._bin.nmcli, 'device', 'wifi', 'rescan', 'ifname', interface]

    def wifi_list(self, interface: str) -> Argv:
        return [self._bin.nmcli, '-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY',
                'device', 'wifi', 'list', 'ifname', interface]

    def wifi_details(self, interface: str) -> Argv:
        return [self._bin.nmcli, '-t', '-f',
                'IN-USE,BSSID,CHAN,FREQ,RATE,SIGNAL,SECURITY',
                'device', 'wifi', 'list', 'ifname', interface]

    def wifi_link(self, interface: str) -> Argv:
        return [self._bin.iw, 'dev', interface, 'link']

    def wifi_info(self, interface: str) -> Argv:
        return [self._bin.iw, 'dev', interface, 'info']

    def wifi_station(self, interface: str) -> Argv:
        return [self._bin.iw, 'dev', interface, 'station', 'dump']

    def wifi_survey(self, interface: str) -> Argv:
        return [self._bin.iw, 'dev', interface, 'survey', 'dump']

    def wifi_delete(self, name: str) -> Argv:
        return [self._bin.nmcli, 'connection', 'delete', 'id', name]

    def wifi_active_uuid(self, interface: str) -> Argv:
        return [self._bin.nmcli, '-g', 'GENERAL.CON-UUID', 'device', 'show', interface]

    def wifi_disconnect(self, interface: str) -> Argv:
        return [self._bin.nmcli, 'device', 'disconnect', interface]

    def wifi_saved(self) -> Argv:
        return [self._bin.nmcli, '-t', '-f', 'UUID,NAME,TYPE', 'connection', 'show']

    def wifi_profile_ssid(self, uuid: str) -> Argv:
        return [self._bin.nmcli, '-e', 'no', '-g', '802-11-wireless.ssid',
                'connection', 'show', 'uuid', uuid]

    def wifi_up_uuid(self, uuid: str, interface: str) -> Argv:
        return [self._bin.nmcli, 'connection', 'up', 'uuid', uuid, 'ifname', interface]

    def wifi_ipv4(self, uuid: str) -> Argv:
        argv = self.ethernet_ipv4(uuid)
        argv.insert(5, 'uuid')
        return argv

    def wifi_set_ipv4(self, uuid: str, config=None) -> Argv:
        argv = (self.set_dhcp(uuid) if config is None else
                self.set_static(uuid, f'{config.address}/{config.prefix}', config.gateway, config.dns))
        argv.insert(3, 'uuid')
        return argv

    def wifi_delete_uuid(self, uuid: str) -> Argv:
        return [self._bin.nmcli, 'connection', 'delete', 'uuid', uuid]

    def wifi_connect(self, interface: str, ssid: str, password: str) -> Argv:
        argv = [self._bin.nmcli, 'device', 'wifi', 'connect', ssid]
        if password:
            argv += ['password', password]
        argv += ['ifname', interface]
        return argv

    def wifi_add_secured(self, interface: str, ssid: str, password: str) -> Argv:
        # key-mgmt y psk juntos. Si falta key-mgmt, NetworkManager dice
        # "security key management property is missing".
        return [self._bin.nmcli, 'connection', 'add', 'type', 'wifi',
                'ifname', interface, 'con-name', ssid, 'ssid', ssid,
                '802-11-wireless-security.key-mgmt', 'wpa-psk',
                '802-11-wireless-security.psk', password]

    def wifi_set_psk(self, name: str, password: str) -> Argv:
        return [self._bin.nmcli, 'connection', 'modify', name,
                '802-11-wireless-security.key-mgmt', 'wpa-psk',
                '802-11-wireless-security.psk', password]

    def wifi_up(self, name: str, interface: str) -> Argv:
        return [self._bin.nmcli, 'connection', 'up', name, 'ifname', interface]
