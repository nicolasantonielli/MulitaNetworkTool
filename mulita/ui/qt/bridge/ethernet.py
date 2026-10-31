from __future__ import annotations

import ipaddress

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.errors import ValidationError
from mulita.core.models import AddressMode, EthernetConfig
from mulita.presentation.i18n import tr
from mulita.ui.qt.bridge.base import TaskController


def _netmask(config: EthernetConfig) -> str:
    if not config.address:
        return ''
    return str(ipaddress.IPv4Network(f'0.0.0.0/{config.prefix}').netmask)


class InternalEthernetController(TaskController):
    """DHCP o IP fija de la ethernet interna."""
    loaded = pyqtSignal()

    def __init__(self, ctx, wifi=False):
        super().__init__(ctx)
        self._network = ctx.services.wifi if wifi else ctx.services.ethernet
        self._wifi = wifi
        self._config = EthernetConfig()
        ctx.services.settings.subscribe(lambda _settings: self.loaded.emit())

    @pyqtProperty(str, notify=loaded)
    def interfaceName(self) -> str:
        return 'Wi-Fi' if self._wifi else self._network.interface

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
            return tr('inUseStatic', address=self._config.address, prefix=self._config.prefix)
        if self._config.address:
            return tr('inUseDhcpAddr', address=self._config.address)
        return tr('inUseDhcp')

    @pyqtProperty('QVariantList', constant=True)
    def modes(self) -> list[dict]:
        return [{'label': mode.label, 'value': mode.value} for mode in AddressMode]

    @pyqtSlot()
    def refresh(self) -> None:
        self._task(self._network.read if self._wifi else self._network.read_with_vlan, self._show)

    @pyqtProperty(int, notify=loaded)
    def vlanId(self) -> int:
        return 0 if self._wifi else self._network.vlan_id

    @pyqtSlot(str, str, str, str, str, bool, str)
    def applyVlan(self, mode, address, netmask, gateway, dns, enabled, vlan) -> None:
        if self._wifi:
            return
        def ok(config):
            self._show(config)
            self._ctx.notifier.success(tr('ethInternal'), tr('vlanApplied'))
        self._task(lambda: self._network.apply_with_vlan(
            mode, address, netmask, gateway, dns, enabled, vlan), ok)

    @pyqtSlot(str, str, str, str, str)
    def apply(self, mode: str, address: str, netmask: str, gateway: str, dns: str) -> None:
        if mode == AddressMode.DHCP.value:
            task = self._network.apply_dhcp
            done = tr('dhcpOn')
        elif mode == AddressMode.ESTATICA.value:
            task = lambda: self._network.apply_static(address, netmask, gateway, dns)
            done = tr('staticApplied')
        else:
            self._fail(ValidationError(tr('invalidMode', mode=mode)))
            return

        def ok(config: EthernetConfig) -> None:
            self._show(config)
            self._ctx.notifier.success(tr('wifiIp' if self._wifi else 'ethInternal'), done)

        self._task(task, ok)

    def _show(self, config: EthernetConfig) -> None:
        self._config = config
        self.loaded.emit()
