from __future__ import annotations

import json

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.models import ClimateReading, SpeedTestResult
from mulita.core.errors import MulitaError, ValidationError
from mulita.presentation import texts
from mulita.presentation.i18n import tr
from mulita.ui.qt.bridge.base import BridgeContext, TaskController


class WakeOnLanController(TaskController):
    changed = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._phase = ''
        self._mac = ''
        self._target = ''
        self._port = ''
        self._detail = ''

    @pyqtProperty(str, notify=changed)
    def phase(self) -> str:
        return self._phase

    @pyqtProperty(str, notify=changed)
    def mac(self) -> str:
        return self._mac

    @pyqtProperty(str, notify=changed)
    def target(self) -> str:
        return self._target

    @pyqtProperty(str, notify=changed)
    def port(self) -> str:
        return self._port

    @pyqtProperty(str, notify=changed)
    def detail(self) -> str:
        return self._detail

    @pyqtSlot(str)
    def wake(self, mac: str) -> None:
        self._mac = (mac or '').strip().upper()
        self._target = ''
        self._port = ''
        self._detail = ''
        self._phase = 'sending'
        self.changed.emit()
        self._task(lambda: self._services.wake_on_lan.wake(mac), self._sent, self._failed)

    def _sent(self, packet) -> None:
        self._phase = 'sent'
        self._mac = packet.mac
        self._target = packet.target
        self._port = packet.port
        self._detail = ''
        self.changed.emit()

    def _failed(self, error: Exception) -> None:
        self._phase = 'error'
        self._detail = str(error)
        self.changed.emit()


class ClimateController(TaskController):
    readingChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._reading: ClimateReading | None = None
        self._read = False

    @pyqtProperty(str, notify=readingChanged)
    def temperature(self) -> str:
        return texts.temperature_value(self._reading)

    @pyqtProperty(str, notify=readingChanged)
    def humidity(self) -> str:
        return texts.humidity_value(self._reading)

    @pyqtProperty(str, notify=readingChanged)
    def status(self) -> str:
        if self._read and self._reading is None:
            return 'El sensor no respondio. Intente de nuevo.'
        return ''

    @pyqtSlot()
    def refresh(self) -> None:
        self._task(self._services.climate.read, self._show, lambda _error: self._show(None))

    def _show(self, reading: ClimateReading | None) -> None:
        self._reading = reading
        self._read = True
        self.readingChanged.emit()


class SpeedTestController(TaskController):
    resultChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._result: SpeedTestResult | None = None
        self._status = ''

    @pyqtProperty(str, notify=resultChanged)
    def download(self) -> str:
        return texts.mbps(self._result.download_bps) if self._result else texts.NO_VALUE

    @pyqtProperty(str, notify=resultChanged)
    def upload(self) -> str:
        return texts.mbps(self._result.upload_bps) if self._result else texts.NO_VALUE

    @pyqtProperty(str, notify=resultChanged)
    def status(self) -> str:
        return self._status

    @pyqtSlot()
    def measure(self) -> None:
        self._set_status(texts.MEASURING)
        self._task(self._services.speed_test.measure, self._show, lambda error: self._set_status(str(error)))

    def _show(self, result: SpeedTestResult) -> None:
        self._result = result
        self._set_status('')

    def _set_status(self, status: str) -> None:
        self._status = status
        self.resultChanged.emit()


class PublicIpController(TaskController):
    addressChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._info = None
        self._status = ''
        ctx.services.settings.subscribe(lambda _settings: self.addressChanged.emit())

    @pyqtProperty(str, notify=addressChanged)
    def address(self) -> str:
        return self._info.ip if self._info else texts.NO_VALUE

    @pyqtProperty(str, notify=addressChanged)
    def factsJson(self) -> str:
        if self._info is None:
            return '[]'
        return json.dumps([
            {'label': label, 'value': value} for label, value in self._info.facts()
        ])

    @pyqtProperty(str, notify=addressChanged)
    def status(self) -> str:
        return self._status

    @pyqtSlot()
    def lookup(self) -> None:
        self._task(self._services.public_ip.lookup, self._show, self._failed)

    @pyqtSlot()
    def save(self) -> None:
        info = self._info
        if info is None or self._busy:
            return
        try:
            name = self._services.public_ip.save(info)
        except MulitaError as exc:
            self._fail(exc)
            return
        self._ctx.notifier.success(tr('pubTitle'), name)

    def _show(self, info) -> None:
        self._info, self._status = info, ''
        self.addressChanged.emit()

    def _failed(self, error: Exception) -> None:
        self._status = str(error)
        self.addressChanged.emit()


class MacVendorController(TaskController):
    vendorChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._vendor = ''
        self._status = ''

    @pyqtProperty(str, notify=vendorChanged)
    def vendor(self) -> str:
        return self._vendor or texts.NO_VALUE

    @pyqtProperty(str, notify=vendorChanged)
    def status(self) -> str:
        return self._status

    @pyqtSlot(str)
    def lookup(self, mac: str) -> None:
        self._task(lambda: self._services.mac_vendor.lookup(mac), self._show, self._failed)

    def _show(self, name: str) -> None:
        self._vendor, self._status = name, ''
        self.vendorChanged.emit()

    def _failed(self, error: Exception) -> None:
        self._vendor, self._status = '', str(error)
        self.vendorChanged.emit()


def _picked(payload: str) -> list[tuple[str, str]]:
    try:
        data = json.loads(payload or '[]')
    except json.JSONDecodeError as exc:
        raise ValidationError(tr('noFilesSelected')) from exc
    items = []
    for row in data if isinstance(data, list) else []:
        if not isinstance(row, dict):
            continue
        place = str(row.get('place') or '')
        name = str(row.get('name') or '')
        if place and name:
            items.append((place, name))
    if not items:
        raise ValidationError(tr('noFilesSelected'))
    return items


class FilesController(TaskController):
    filesChanged = pyqtSignal()
    drivesChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext):
        super().__init__(ctx)
        self._files: tuple = ()
        self._drives: tuple = ()

    @pyqtProperty(str, notify=filesChanged)
    def filesJson(self) -> str:
        return json.dumps([{
            'place': item.place,
            'placeLabel': item.place_label,
            'name': item.name,
            'size': item.size,
            'modified': item.modified,
        } for item in self._files])

    @pyqtProperty(str, notify=drivesChanged)
    def drivesJson(self) -> str:
        return json.dumps([
            {'label': item.label, 'value': item.device} for item in self._drives
        ])

    @pyqtSlot()
    def refresh(self) -> None:
        self._task(self._services.files.list_files, self._show)

    @pyqtSlot()
    def refreshDrives(self) -> None:
        self._task(self._services.files.list_drives, self._show_drives)

    @pyqtSlot(str, str, str)
    def rename(self, place: str, name: str, new_name: str) -> None:
        self._task(lambda: self._services.files.rename(place, name, new_name), self._done)

    @pyqtSlot(str, str, str)
    def copyFile(self, place: str, name: str, new_name: str) -> None:
        self._task(lambda: self._services.files.copy(place, name, new_name), self._done)

    @pyqtSlot(str, str)
    def remove(self, place: str, name: str) -> None:
        self._task(lambda: self._services.files.delete(place, name), self._done)

    @pyqtSlot(str)
    def removeMany(self, payload: str) -> None:
        self._task(lambda: self._services.files.delete_many(_picked(payload)), self._done)

    @pyqtSlot(str, str, str)
    def exportFile(self, place: str, name: str, drive: str) -> None:
        self._task(lambda: self._services.files.export(place, name, drive), self._done)

    @pyqtSlot(str, str)
    def exportMany(self, payload: str, drive: str) -> None:
        self._task(lambda: self._services.files.export_many(_picked(payload), drive), self._done)

    def _show(self, found: tuple) -> None:
        self._files = found
        self.filesChanged.emit()

    def _show_drives(self, found: tuple) -> None:
        self._drives = found
        self.drivesChanged.emit()

    def _done(self, _name) -> None:
        self._ctx.notifier.success(tr('filesTitle'), tr('filesReady'))
        self.refresh()
