from __future__ import annotations

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.models import WifiNetwork
from mulita.ui.qt.bridge.base import TaskController


class WifiController(TaskController):
    """Redes Wi-Fi visibles y la conexion elegida."""
    networksChanged = pyqtSignal()

    def __init__(self, ctx):
        super().__init__(ctx)
        self._device = ''
        self._networks: tuple[WifiNetwork, ...] = ()

    @pyqtProperty(str, notify=networksChanged)
    def deviceName(self) -> str:
        return self._device

    @pyqtProperty(str, notify=networksChanged)
    def activeName(self) -> str:
        for network in self._networks:
            if network.active:
                return network.ssid
        return ''

    @pyqtProperty('QVariantList', notify=networksChanged)
    def networks(self) -> list[dict]:
        return [{
            'ssid': network.ssid,
            'signal': network.signal,
            'security': network.security or 'Abierta',
            'secure': network.secure,
            'active': network.active,
        } for network in self._networks]

    @pyqtSlot()
    def refresh(self) -> None:
        self._task(self._services.wifi.scan, self._show)

    @pyqtSlot(str, str, bool)
    def connectTo(self, ssid: str, password: str, secure: bool) -> None:
        def connected(name: str) -> None:
            self._ctx.notifier.success('Wi-Fi', f'Conectado a {name}')
            self.refresh()

        self._task(lambda: self._services.wifi.connect(ssid, password, secure), connected)

    def _show(self, found: tuple[str | None, tuple[WifiNetwork, ...]]) -> None:
        device, networks = found
        self._device = device or ''
        self._networks = networks
        self.networksChanged.emit()
