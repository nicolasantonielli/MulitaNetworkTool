from __future__ import annotations

import ipaddress

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.errors import ValidationError
from mulita.core.models import AddressMode, EthernetConfig
from mulita.ui.qt.bridge.base import TaskController
from mulita.core.ipv4 import IPv4Configuration


def _netmask(config: EthernetConfig) -> str:
    if not config.address:
        return ''
    return str(ipaddress.IPv4Network(f'0.0.0.0/{config.prefix}').netmask)


class IPv4Controller(TaskController):
    """Presentación IPv4 compartida sin decisiones sobre el tipo de conexión."""
    loaded = pyqtSignal()
    presentationChanged = pyqtSignal()

    def __init__(self, ctx, network: IPv4Configuration, interface_name, title_key: str):
        super().__init__(ctx)
        self._network = network
        self._interface_name = interface_name
        self._title_key = title_key
        self._config = EthernetConfig()
        ctx.settings.subscribe(lambda _settings: self.presentationChanged.emit())

    @pyqtProperty(str, notify=loaded)
    def interfaceName(self) -> str:
        return self._interface_name()

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

    @pyqtProperty(str, notify=presentationChanged)
    def summary(self) -> str:
        if self._config.mode is AddressMode.ESTATICA and self._config.address:
            return self._tr('inUseStatic', address=self._config.address, prefix=self._config.prefix)
        if self._config.address:
            return self._tr('inUseDhcpAddr', address=self._config.address)
        return self._tr('inUseDhcp')

    @pyqtProperty('QVariantList', constant=True)
    def modes(self) -> list[dict]:
        return [{'label': mode.label, 'value': mode.value} for mode in AddressMode]

    @pyqtSlot()
    def refresh(self) -> None:
        self._task(self._network.read, self._show)

    @pyqtSlot(str, str, str, str, str)
    def apply(self, mode: str, address: str, netmask: str, gateway: str, dns: str) -> None:
        if mode == AddressMode.DHCP.value:
            task = self._network.apply_dhcp
            done = self._tr('dhcpOn')
        elif mode == AddressMode.ESTATICA.value:
            task = lambda: self._network.apply_static(address, netmask, gateway, dns)
            done = self._tr('staticApplied')
        else:
            self._fail(ValidationError(self._tr('invalidMode', mode=mode)))
            return

        def ok(config: EthernetConfig) -> None:
            self._show(config)
            self._note_ipv4(config)
            self._ctx.notifier.success(self._tr(self._title_key), done)

        self._task(task, ok, action=self._title_key, detail=f'{mode} {address}'.strip())

    def _note_ipv4(self, config):
        assigned = f'{config.address}/{config.prefix}' if config.address else 'sin dirección asignada'
        self._note(f'Se aplicó la configuración IPv4 en {self.interfaceName}: {config.mode.value}, {assigned}.')

    def _show(self, config: EthernetConfig) -> None:
        self._config = config
        self.loaded.emit()
        self.presentationChanged.emit()
