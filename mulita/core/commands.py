"""Traduce pedidos del negocio a lineas de comando. Siempre listas, nunca shell."""
from __future__ import annotations

from pathlib import PurePosixPath

from mulita.config import Binaries
from mulita.core.models import CaptureRequest, PingRequest

Argv = list[str]


class CommandFactory:

    def __init__(self, binaries: Binaries):
        self._bin = binaries

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
        return [self._bin.mtr, target, '-n', '-r', '-c', str(cycles)]

    def ping(self, request: PingRequest) -> Argv:
        argv = [self._bin.ping, request.target, '-n']
        if not request.continuous:
            argv += ['-c', str(request.count)]
        argv += ['-i', f'{request.interval:.2f}', '-s', str(request.payload_bytes)]
        return argv

    def port_scan(self, arguments: list[str]) -> Argv:
        return [self._bin.nmap, *arguments]

    def discovery(self) -> Argv:
        # -d no lee ~/.netdiscover. El servicio no trae $HOME y sin esto
        # netdiscover se niega a escanear.
        return [self._bin.netdiscover, '-f', '-P', '-d']

    def wake_on_lan(self, mac: str) -> Argv:
        return [self._bin.wakeonlan, mac]

    def speed_test(self) -> Argv:
        return [self._bin.speedtest, '--json']

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

    def update(self, repository_dir: str, remote: str, branch: str) -> Argv:
        return [self._bin.git, '-C', repository_dir, 'pull', remote, branch]

    def restart_service(self, service_name: str) -> Argv:
        """Fuera del cgroup del servicio: si no, systemd mata el comando al parar la app."""
        return [self._bin.systemd_run, '--collect', '--no-block',
                self._bin.systemctl, 'restart', service_name]

    def poweroff(self) -> Argv:
        return [self._bin.poweroff]
