"""Funciones exclusivas de Ethernet sobre el controlador IPv4 compartido."""
from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot
from mulita.ui.qt.bridge.ipv4 import IPv4Controller


class InternalEthernetController(IPv4Controller):
    vlanLoaded = pyqtSignal()

    def __init__(self, ctx, network):
        super().__init__(ctx, network, lambda: network.interface, 'ethInternal')

    @pyqtSlot()
    def refresh(self) -> None:
        self._task(self._network.read_with_vlan, self._show)

    def _show(self, config):
        super()._show(config)
        self.vlanLoaded.emit()

    @pyqtProperty(int, notify=vlanLoaded)
    def vlanId(self) -> int:
        return self._network.vlan_id

    @pyqtSlot(str, str, str, str, str, bool, str)
    def applyVlan(self, mode, address, netmask, gateway, dns, enabled, vlan) -> None:
        def ok(config):
            self._show(config)
            self._note_ipv4(config)
            self._note(self._tr('journalVlan', vlan=vlan, interface=self.interfaceName) if enabled else
                       self._tr('journalNoVlan', interface=self.interfaceName))
            self._ctx.notifier.success(self._tr('ethInternal'), self._tr('vlanApplied'))
        self._task(lambda: self._network.apply_with_vlan(
            mode, address, netmask, gateway, dns, enabled, vlan), ok, action='ethInternal',
            detail=f'{mode} {address}' + (f' VLAN {vlan}' if enabled else ''))
