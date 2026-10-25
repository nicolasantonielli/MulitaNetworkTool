from __future__ import annotations

import ipaddress

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.errors import ValidationError
from mulita.core.models import AddressMode, EthernetConfig
from mulita.ui.qt.bridge.base import TaskController


def _netmask(config: EthernetConfig) -> str:
    if not config.address:
        return ''
    return str(ipaddress.IPv4Network(f'0.0.0.0/{config.prefix}').netmask)


class InternalEthernetController(TaskController):
    """DHCP o IP fija de la ethernet interna."""
    loaded = pyqtSignal()

    def __init__(self, ctx):
        super().__init__(ctx)
        self._config = EthernetConfig()

    @pyqtProperty(str, notify=loaded)
    def interfaceName(self) -> str:
        return self._services.ethernet.interface

    @pyqtProperty(str, notify=loaded)
    def mode(self) -> str:
        return self._config.mode.value

    @pyqtProperty(str, notify=loaded)
    def address(self) -> str:
        return self._config.address

    @pyqtProperty(str, notify=loaded)
    def netmask(self) -> str:
        return _netmask(self._config)

    @pyqtProperty(str, notify=loaded)
    def gateway(self) -> str:
        return self._config.gateway

    @pyqtProperty(str, notify=loaded)
    def dns(self) -> str:
        return self._config.dns

    @pyqtProperty(str, notify=loaded)
    def summary(self) -> str:
        if self._config.mode is AddressMode.ESTATICA and self._config.address:
            return f'En uso: {self._config.address}/{self._config.prefix}'
        if self._config.address:
            return f'En uso: DHCP · {self._config.address}'
        return 'En uso: DHCP'

    @pyqtProperty('QVariantList', constant=True)
    def modes(self) -> list[dict]:
        return [{'label': mode.label, 'value': mode.value} for mode in AddressMode]

    @pyqtSlot()
    def refresh(self) -> None:
        self._task(self._services.ethernet.read, self._show)

    @pyqtSlot(str, str, str, str, str)
    def apply(self, mode: str, address: str, netmask: str, gateway: str, dns: str) -> None:
        if mode == AddressMode.DHCP.value:
            task = self._services.ethernet.apply_dhcp
            done = 'DHCP activo'
        elif mode == AddressMode.ESTATICA.value:
            task = lambda: self._services.ethernet.apply_static(address, netmask, gateway, dns)
            done = 'Direccion estatica aplicada'
        else:
            self._fail(ValidationError(f'Modo invalido: {mode}'))
            return

        def ok(config: EthernetConfig) -> None:
            self._show(config)
            self._ctx.notifier.success('Ethernet interna', done)

        self._task(task, ok)

    def _show(self, config: EthernetConfig) -> None:
        self._config = config
        self.loaded.emit()
