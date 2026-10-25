from __future__ import annotations

import json

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.models import WifiLink, WifiNetwork
from mulita.ui.qt.bridge.base import TaskController


class WifiController(TaskController):
    """Redes Wi-Fi visibles y la conexion elegida."""
    networksChanged = pyqtSignal()

    def __init__(self, ctx):
        super().__init__(ctx)
        self._device = ''
        self._networks: tuple[WifiNetwork, ...] = ()
        self._link = WifiLink()

    @pyqtProperty(str, notify=networksChanged)
    def deviceName(self) -> str:
        return self._device

    @pyqtProperty(str, notify=networksChanged)
    def activeName(self) -> str:
        for network in self._networks:
            if network.active:
                return network.ssid
        return ''

    def _rows(self) -> list[dict]:
        return [{
            'ssid': network.ssid,
            'signal': network.signal,
            'security': network.security or 'Abierta',
            'secure': network.secure,
            'active': network.active,
        } for network in self._networks]

    @pyqtProperty(str, notify=networksChanged)
    def networksJson(self) -> str:
        return json.dumps(self._rows())

    @pyqtProperty(str, notify=networksChanged)
    def linkJson(self) -> str:
        return json.dumps([
            {'label': label, 'value': value} for label, value in self._link.facts()
        ])

    @pyqtSlot()
    def refresh(self) -> None:
        self._task(self._services.wifi.scan, self._show)

    @pyqtSlot()
    def loadLink(self) -> None:
        self._task(self._services.wifi.status, self._show_link)

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

    def _show_link(self, link: WifiLink) -> None:
        self._link = link
        self._device = link.interface
        self.networksChanged.emit()
