from __future__ import annotations

import ipaddress
import time
from collections import deque

from PyQt5.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.models import CaptureDirection, NetworkInterface, TapConfig
from mulita.ui.qt.bridge.base import (BridgeContext, Console, Controller,
                                      SessionController)


def primary_address(interfaces: list[NetworkInterface]) -> str:
    """Primera IPv4 util: la que el tecnico necesita ver en la barra de estado."""
    for interface in interfaces:
        for address in interface.addresses:
            try:
                ip = ipaddress.ip_address(address)
            except ValueError:
                continue
            if ip.version == 4 and not ip.is_loopback and not ip.is_link_local:
                return address
    return ''


class NetworkController(Controller):
    interfacesChanged = pyqtSignal()
    primaryAddressChanged = pyqtSignal()
    refreshingChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._interfaces: list[dict] = []
        self._primary = ''
        self._refreshing = False
        self._started = 0.0

    @pyqtProperty('QVariantList', notify=interfacesChanged)
    def interfaces(self) -> list[dict]:
        return self._interfaces

    @pyqtProperty(str, notify=primaryAddressChanged)
    def primaryAddress(self) -> str:
        return self._primary

    @pyqtProperty(bool, notify=refreshingChanged)
    def refreshing(self) -> bool:
        return self._refreshing

    @pyqtSlot()
    def refresh(self) -> None:
        if self._refreshing:
            return
        self._set_refreshing(True)
        self._ctx.dispatcher.background(self._services.interfaces.list_interfaces,
                                        self._loaded, self._failed)

    def _loaded(self, interfaces: list[NetworkInterface]) -> None:
        rows = [{'label': item.name, 'value': item.name, 'linked': item.cable} for item in interfaces]
        if rows != self._interfaces:
            self._interfaces = rows
            self.interfacesChanged.emit()
        primary = primary_address(interfaces)
        if primary != self._primary:
            self._primary = primary
            self.primaryAddressChanged.emit()
        self._set_refreshing(False)

    def _failed(self, _error: Exception) -> None:
        self._set_refreshing(False)

    def _set_refreshing(self, value: bool) -> None:
        if value:
            self._started = time.monotonic()
            self._refreshing = True
            self.refreshingChanged.emit()
            return
        # ip responde al instante. Sin esta espera el boton no llega a decir Leyendo.
        wait = 0.7 - (time.monotonic() - self._started)
        if wait > 0:
            QTimer.singleShot(int(wait * 1000), self._end_refresh)
            return
        self._end_refresh()

    def _end_refresh(self) -> None:
        if not self._refreshing:
            return
        self._refreshing = False
        self.refreshingChanged.emit()


class CaptureController(SessionController):
    activeFileChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx, ctx.services.capture)
        self._last_output: deque[str] = deque(maxlen=3)
        self._stopping = False
        self._active_file = ''

    @pyqtProperty('QVariantList', constant=True)
    def directions(self) -> list[dict]:
        return [{'label': direction.label, 'value': direction.value} for direction in CaptureDirection]

    @pyqtProperty(str, constant=True)
    def defaultFilename(self) -> str:
        return self._ctx.config.default_capture_name

    @pyqtProperty(str, notify=activeFileChanged)
    def activeFile(self) -> str:
        return self._active_file

    @pyqtSlot(str, str, str, result=bool)
    def start(self, interface: str, direction: str, filename: str) -> bool:
        self._last_output.clear()
        self._stopping = False
        started = self._launch(lambda **listeners: self._remember(
            self._session.start(interface, direction, filename, **listeners)))
        return started

    @pyqtSlot()
    def stop(self) -> None:
        self._stopping = True
        super().stop()

    def _remember(self, request) -> None:
        self._active_file = request.filename
        self.activeFileChanged.emit()

    def _output(self, text: str) -> None:
        self._last_output.append(text)

    def _rejected(self, error) -> None:
        self._fail(error)

    def _finished(self, code: int) -> None:
        if code != 0 and not self._stopping:
            detail = ''.join(self._last_output).strip() or f'tcpdump termino con codigo {code}'
            folder = str(self._ctx.config.capture_dir)
            detail = detail.replace(folder + '/', '').replace(folder, 'la carpeta de capturas')
            self._ctx.notifier.error(detail, title='Captura')


class TapController(Controller):
    runningChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._console = Console()

    @pyqtProperty(bool, notify=runningChanged)
    def running(self) -> bool:
        return self._services.tap.is_running

    @pyqtProperty(QObject, constant=True)
    def console(self) -> Console:
        return self._console

    @pyqtSlot(str, str, str)
    def start(self, entrante: str, mirror: str, saliente: str) -> None:
        self._services.tap.start(TapConfig(entrante=entrante, mirror=mirror, saliente=saliente))
        self.runningChanged.emit()

    @pyqtSlot()
    def stop(self) -> None:
        self._services.tap.stop()
        self.runningChanged.emit()
