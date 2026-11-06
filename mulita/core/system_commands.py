"""Comandos del sistema: almacenamiento USB, teclado, actualizacion y apagado."""
from __future__ import annotations

from mulita.core.command_base import Argv, CommandBase


class SystemCommands(CommandBase):

    def usb_block_devices(self) -> Argv:
        return [self._bin.lsblk, '-J', '-o', 'NAME,TRAN,LABEL,MOUNTPOINT,TYPE']

    def mount_partition(self, device: str, target: str) -> Argv:
        return [self._bin.mount, f'/dev/{device}', target]

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
