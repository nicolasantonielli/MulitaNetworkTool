"""Traduce pedidos del negocio a lineas de comando. Siempre listas, nunca shell."""
from __future__ import annotations

from pathlib import Path, PurePosixPath

from mulita.config import Binaries
from mulita.core.models import CaptureRequest, PingRequest

Argv = list[str]
SERVERS_DIR = Path(__file__).resolve().parent.parent / 'servers'


class CommandFactory:

    def __init__(self, binaries: Binaries):
        self._bin = binaries

    def _script(self, name: str) -> Argv:
        """Servidores propios (TFTP, web, NTP): scripts de la biblioteca estandar, sin salida diferida."""
        return [self._bin.python, '-u', str(SERVERS_DIR / f'{name}.py')]

    def _dnsmasq_base(self, pid_file: str) -> Argv:
        # --conf-file=/dev/null ignora /etc/dnsmasq.conf. --user=root evita problemas de permisos
        # sobre la carpeta de estado. Cada instancia usa su propio pid para no pisar la del sistema.
        return [self._bin.dnsmasq, '--keep-in-foreground', '--conf-file=/dev/null',
                f'--pid-file={pid_file}', '--user=root', '--no-hosts', '--log-facility=-']

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

    def iperf_server(self, port: int, bind: str = '', one_off: bool = False) -> Argv:
        argv = [self._bin.iperf3, '-s', '-p', str(port), '--forceflush']
        if bind:
            argv += ['-B', bind]
        if one_off:
            argv.append('-1')
        return argv

    def tftp_server(self, root: str, port: int, bind: str = '', writable: bool = True) -> Argv:
        argv = self._script('tftp') + ['--root', root, '--port', str(port)]
        if bind:
            argv += ['--bind', bind]
        if writable:
            argv.append('--writable')
        return argv

    def web_server(self, root: str, http_port: int, https_port: int, bind: str = '',
                   captures: str = '', cert: str = '', key: str = '') -> Argv:
        """Un puerto en cero deja ese protocolo apagado."""
        argv = self._script('web') + ['--root', root,
                                      '--http-port', str(http_port), '--https-port', str(https_port)]
        if bind:
            argv += ['--bind', bind]
        if captures:
            argv += ['--captures', captures]
        if https_port:
            argv += ['--cert', cert, '--key', key]
        return argv

    def ntp_server(self, port: int, stratum: int, bind: str = '') -> Argv:
        argv = self._script('ntp') + ['--port', str(port), '--stratum', str(stratum)]
        if bind:
            argv += ['--bind', bind]
        return argv

    def dns_server(self, address: str, port: int, name: str, answer: str,
                   upstream: str, pid_file: str) -> Argv:
        # --cache-size=0 deja pasar cada consulta, asi el registro muestra todo lo que pide el equipo.
        argv = self._dnsmasq_base(pid_file) + [
            f'--port={port}', '--no-resolv', '--cache-size=0',
            '--log-queries', f'--address=/{name}/{answer}']
        if address:
            argv += [f'--listen-address={address}', '--bind-interfaces']
        if upstream:
            argv.append(f'--server={upstream}')
        return argv

    def dhcp_server(self, interface: str, first: str, last: str, netmask: str, hours: int,
                    gateway: str, dns: str, leases: str, pid_file: str) -> Argv:
        # --port=0 apaga el DNS de esta instancia. --bind-interfaces la limita a un solo puerto.
        return self._dnsmasq_base(pid_file) + [
            '--port=0', '--no-resolv', '--bind-interfaces', f'--interface={interface}',
            f'--dhcp-range={first},{last},{netmask},{hours}h',
            f'--dhcp-option=option:router,{gateway}',
            f'--dhcp-option=option:dns-server,{dns}',
            f'--dhcp-leasefile={leases}', '--dhcp-authoritative', '--log-dhcp']

    def sftp_server(self, config: str) -> Argv:
        return [self._bin.sshd, '-D', '-e', '-f', config]

    def ssh_host_key(self, path: str) -> Argv:
        return [self._bin.ssh_keygen, '-q', '-t', 'ed25519', '-N', '', '-f', path]

    def tls_certificate(self, certificate: str, key: str) -> Argv:
        return [self._bin.openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256',
                '-days', '3650', '-subj', '/CN=mulita', '-keyout', key, '-out', certificate]

    def user_entry(self, name: str) -> Argv:
        return [self._bin.getent, 'passwd', name]

    def user_add(self, name: str, comment: str) -> Argv:
        return [self._bin.useradd, '--no-create-home', '--home-dir', '/',
                '--shell', '/usr/sbin/nologin', '--comment', comment, name]

    def user_delete(self, name: str) -> Argv:
        return [self._bin.userdel, '--force', name]

    def set_password(self) -> Argv:
        """Lee `usuario:clave` de la entrada estandar."""
        return [self._bin.chpasswd]

    def change_owner(self, owner: str, path: str, recursive: bool = False) -> Argv:
        argv = [self._bin.chown]
        if recursive:
            argv.append('-R')
        return argv + [owner, path]

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

    def update(self, repository_dir: str, remote: str, branch: str) -> Argv:
        return [self._bin.git, '-C', repository_dir, 'pull', remote, branch]

    def restart_service(self, service_name: str) -> Argv:
        """Fuera del cgroup del servicio: si no, systemd mata el comando al parar la app."""
        return [self._bin.systemd_run, '--collect', '--no-block',
                self._bin.systemctl, 'restart', service_name]

    def poweroff(self) -> Argv:
        return [self._bin.poweroff]
