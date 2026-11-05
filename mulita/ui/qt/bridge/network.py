from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mulita.services.network import InterfaceService
    from mulita.services.network import CaptureService
    from mulita.services.network import TapService

import ipaddress
import time
from collections import deque

from PyQt5.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.models import CaptureDirection, NetworkInterface, TapConfig
from mulita.core.parsing.network import is_wifi_interface
from mulita.ui.qt.bridge.base import (BridgeContext, Console, Controller,
                                      SessionController)


def _interface_ipv4(interface: NetworkInterface) -> str:
    for address in interface.addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if ip.version == 4 and not ip.is_loopback and not ip.is_link_local:
            return address
    return ''


def primary_address(interfaces: list[NetworkInterface]) -> str:
    """Primera IPv4 util entre todas las interfaces."""
    for interface in interfaces:
        address = _interface_ipv4(interface)
        if address:
            return address
    return ''


class NetworkController(Controller):
    interfacesChanged = pyqtSignal()
    primaryAddressChanged = pyqtSignal()
    refreshingChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext, interfaces: InterfaceService):
        super().__init__(ctx)
        self._interface_service = interfaces
        self._interfaces: list[dict] = []
        self._primary = ''
        self._refreshing = False
        self._started = 0.0

    @pyqtProperty('QVariantList', notify=interfacesChanged)
    def interfaces(self) -> list[dict]:
        return self._interfaces

    @pyqtProperty(str, notify=interfacesChanged)
    def wifiAddress(self) -> str:
        return next((row['address'] for row in self._interfaces
                     if row['address'] and is_wifi_interface(row['value'])), '')

    @pyqtProperty(str, notify=interfacesChanged)
    def ethernetAddress(self) -> str:
        preferred = self._ctx.config.internal_interface
        fallback = ''
        for row in self._interfaces:
            name = row['value']
            if name == preferred and row['address']:
                return row['address']
            if not fallback and name.startswith(('eth', 'en')):
                fallback = row['address']
        return fallback

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
        self._ctx.dispatcher.background(self._interface_service.list_interfaces,
                                        self._loaded, self._failed)

    def _loaded(self, interfaces: list[NetworkInterface]) -> None:
        rows = [{
            'label': item.name,
            'value': item.name,
            'linked': item.cable,
            'address': _interface_ipv4(item),
        } for item in interfaces]
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

    def __init__(self, ctx: BridgeContext, capture: CaptureService):
        super().__init__(ctx, capture)
        self._capture = capture
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
            self._session.start(interface, direction, filename, **listeners)), 'captureTitle', interface)
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
        if self._active_file and (code == 0 or self._stopping):
            self._note(f'La captura de {self._activity_detail} se guardó en {self._active_file}.')
        if code != 0 and not self._stopping:
            detail = ''.join(self._last_output).strip() or self._tr('captureEnded', code=code)
            folder = str(self._ctx.config.capture_dir)
            detail = detail.replace(folder + '/', '').replace(folder, self._tr('captureFolder'))
            self._ctx.notifier.error(detail, title=self._tr('captureTitle'))


class TapController(Controller):
    runningChanged = pyqtSignal()
    activeFileChanged = pyqtSignal()
    linesChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext, tap: TapService):
        super().__init__(ctx)
        self._tap = tap
        self._active_file = ''
        self._lines: list[str] = []
        self._pending = ''

    @pyqtProperty(bool, notify=runningChanged)
    def running(self) -> bool:
        return self._tap.is_running

    @pyqtProperty(str, notify=linesChanged)
    def linesJson(self) -> str:
        return self._json(self._lines)

    @pyqtProperty(str, constant=True)
    def defaultFilename(self) -> str:
        return self._ctx.config.default_capture_name

    @pyqtProperty(str, notify=activeFileChanged)
    def activeFile(self) -> str:
        return self._active_file

    @pyqtSlot(str, str, str, str)
    def start(self, entrante: str, mirror: str, saliente: str, filename: str) -> None:
        from mulita.core.errors import MulitaError
        interfaces = f'{entrante} / {mirror} / {saliente}'
        try:
            name = self._tap.start(
                TapConfig(entrante=entrante, mirror=mirror, saliente=saliente),
                filename,
                on_output=self._ctx.dispatcher.wrap(self._output),
                on_exit=self._ctx.dispatcher.wrap(self._capture_stopped))
        except MulitaError as exc:
            self._record('homeTap', interfaces, 'activityFailed')
            self._fail(exc)
            return
        self._lines = []
        self._pending = ''
        self.linesChanged.emit()
        self._active_file = name
        if name:
            self._note(f'El TAP graba el tráfico en {name}.')
        self._record('homeTap', interfaces, 'activityStarted')
        self.activeFileChanged.emit()
        self.runningChanged.emit()

    @pyqtSlot()
    def stop(self) -> None:
        was_running = self._tap.is_running
        self._tap.stop()
        if was_running:
            self._record('homeTap', '', 'activityEnded')
        self._active_file = ''
        self.activeFileChanged.emit()
        self.runningChanged.emit()

    def _output(self, text: str) -> None:
        folder = str(self._ctx.config.capture_dir / 'tap')
        cleaned = text.replace(folder + '/', '').replace(folder, '').replace('\r', '')
        self._pending += cleaned
        while '\n' in self._pending:
            line, self._pending = self._pending.split('\n', 1)
            self._take(line)
        self.linesChanged.emit()

    def _take(self, line: str) -> None:
        text = line.strip()
        if text:
            self._lines.append(text)

    def _capture_stopped(self, code: int) -> None:
        if self._pending.strip():
            self._take(self._pending)
            self._pending = ''
            self.linesChanged.emit()
        if code != 0 and self._tap.is_running:
            self._ctx.notifier.error(self._tr('tapStopped'), title='TAP')
