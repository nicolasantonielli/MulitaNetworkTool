"""Rutas de los ejecutables externos. Vive en core para que los comandos no dependan de la configuracion."""
from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Binaries:
    tcpdump: str = '/bin/tcpdump'
    mtr: str = '/bin/mtr'
    ping: str = '/bin/ping'
    nmap: str = '/bin/nmap'
    netdiscover: str = '/sbin/netdiscover'
    wakeonlan: str = '/bin/wakeonlan'
    speedtest: str = '/bin/speedtest'
    curl: str = '/bin/curl'
    ip: str = '/usr/bin/ip'
    tc: str = '/usr/sbin/tc'
    mount: str = '/usr/bin/mount'
    lsblk: str = '/usr/bin/lsblk'
    git: str = '/usr/bin/git'
    bash: str = '/bin/bash'
    nmcli: str = '/usr/bin/nmcli'
    iw: str = '/usr/sbin/iw'
    systemctl: str = '/usr/bin/systemctl'
    systemd_run: str = '/usr/bin/systemd-run'
    iperf3: str = '/usr/bin/iperf3'
    dnsmasq: str = '/usr/sbin/dnsmasq'
    sshd: str = '/usr/sbin/sshd'
    ssh_keygen: str = '/usr/bin/ssh-keygen'
    openssl: str = '/usr/bin/openssl'
    testssl: str = '/usr/bin/testssl'
    getent: str = '/usr/bin/getent'
    useradd: str = '/usr/sbin/useradd'
    userdel: str = '/usr/sbin/userdel'
    chpasswd: str = '/usr/sbin/chpasswd'
    chown: str = '/usr/bin/chown'
    runuser: str = '/usr/sbin/runuser'
    python: str = sys.executable or 'python3'
    onboard: str = 'onboard'
    killall: str = 'killall'
    poweroff: str = 'poweroff'
