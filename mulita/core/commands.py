"""Traduce pedidos del negocio a lineas de comando. Siempre listas, nunca shell."""
from __future__ import annotations

from pathlib import PurePosixPath
from mulita.core.server_commands import ServerCommands

from mulita.core.binaries import Binaries
from mulita.core.models import CaptureRequest, PingRequest

Argv = list[str]


class CommandFactory(ServerCommands):

    def __init__(self, binaries: Binaries, server_programs: PurePosixPath | None = None):
        super().__init__(binaries, server_programs)

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

    def usb_block_devices(self) -> Argv:
        return [self._bin.lsblk, '-J', '-o', 'NAME,TRAN,LABEL,MOUNTPOINT,TYPE']

    def mount_partition(self, device: str, target: str) -> Argv:
        return [self._bin.mount, f'/dev/{device}', target]

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

    def capture(self, request: CaptureRequest, directory: PurePosixPath) -> Argv:
        return [self._bin.tcpdump,
                '-Q', request.direction.value,
                '-i', request.interface,
                '-w', str(directory / request.filename)]

    def trace(self, target: str, cycles: int) -> Argv:
        return [self._bin.mtr, target, '-n', '-r', '--csv', '-c', str(cycles)]

    def ping(self, request: PingRequest) -> Argv:
        argv = [self._bin.ping, request.target, '-n']
        if not request.continuous:
            argv += ['-c', str(request.count)]
        argv += ['-i', f'{request.interval:.2f}', '-s', str(request.payload_bytes)]
        return argv

    def port_scan(self, arguments: list[str]) -> Argv:
        return [self._bin.nmap, *arguments]

    def nmap(self, arguments: list[str]) -> Argv:
        return [self._bin.nmap, *arguments]

    def discovery(self, interface: str = '', network: str = '') -> Argv:
        # -d no lee ~/.netdiscover. -L deja la salida parseable y sigue
        # escuchando. Sin -f recorre toda la red, no solo .1 .100 y .254.
        argv = [self._bin.netdiscover, '-L', '-N', '-d']
        if interface:
            argv += ['-i', interface]
        if network:
            argv += ['-r', network]
        return argv

    def tls_scan(self, target: str, flags: list[str], report: str) -> Argv:
        # --warnings batch evita las preguntas, --color 0 deja texto plano y
        # --ip one prueba una sola direccion aunque el nombre tenga varias.
        return [self._bin.testssl, '--quiet', '--color', '0', '--warnings', 'batch',
                '--connect-timeout', '10', '--openssl-timeout', '10', '--ip', 'one',
                '--jsonfile', report, *flags, target]

    def wake_on_lan(self, mac: str) -> Argv:
        return [self._bin.wakeonlan, mac]

    def speed_test(self, source: str = '') -> Argv:
        argv = [self._bin.speedtest, '--json', '--timeout', '25']
        if source:
            argv += ['--source', source]
        return argv

    def rule_add_from(self, source: str, table: str) -> Argv:
        return [self._bin.ip, 'rule', 'add', 'from', source, 'lookup', table, 'priority', '50']

    def rule_del_from(self, source: str, table: str) -> Argv:
        return [self._bin.ip, 'rule', 'del', 'from', source, 'lookup', table, 'priority', '50']

    def route_replace_default(self, gateway: str, interface: str, table: str) -> Argv:
        return [self._bin.ip, 'route', 'replace', 'default', 'via', gateway,
                'dev', interface, 'onlink', 'table', table]

    def route_flush_table(self, table: str) -> Argv:
        return [self._bin.ip, 'route', 'flush', 'table', table]

    def public_ip(self, url: str, timeout: int) -> Argv:
        return [self._bin.curl, '-s', '--max-time', str(timeout), url]

    def mac_vendor(self, url: str, mac: str, timeout: int) -> Argv:
        # El codigo HTTP va al final de la salida. 404 y 429 no son un fallo de curl.
        return [self._bin.curl, '-sS', '--max-time', str(timeout),
                '-w', '\n%{http_code}', f'{url.rstrip("/")}/{mac}']

    def keyboard(self) -> Argv:
        return [self._bin.onboard]

    def hide_keyboard(self) -> Argv:
        return [self._bin.killall, 'onboard']

    def update(self, repository_dir: str, remote: str, branch: str, user: str = '') -> Argv:
        argv = [self._bin.git, '-C', repository_dir, 'pull', remote, branch]
        return [self._bin.runuser, '-u', user, '--', *argv] if user else argv

    def restart_service(self, service_name: str) -> Argv:
        """Fuera del cgroup del servicio: si no, systemd mata el comando al parar la app."""
        return [self._bin.systemd_run, '--collect', '--no-block',
                self._bin.systemctl, 'restart', service_name]

    def poweroff(self) -> Argv:
        return [self._bin.poweroff]
