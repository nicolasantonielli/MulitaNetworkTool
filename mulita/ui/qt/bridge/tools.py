from __future__ import annotations

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.models import ClimateReading, SpeedTestResult
from mulita.presentation import texts
from mulita.ui.qt.bridge.base import BridgeContext, TaskController


class WakeOnLanController(TaskController):

    @pyqtSlot(str)
    def wake(self, mac: str) -> None:
        self._console.clear()
        self._task(lambda: self._services.wake_on_lan.wake(mac),
                   self._console.show, lambda error: self._console.show(f'{error}\n'))


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
        self._address = ''
        self._status = ''

    @pyqtProperty(str, notify=addressChanged)
    def address(self) -> str:
        return self._address or texts.NO_VALUE

    @pyqtProperty(str, notify=addressChanged)
    def status(self) -> str:
        return self._status

    @pyqtSlot()
    def lookup(self) -> None:
        self._task(self._services.public_ip.lookup, self._show, self._failed)

    def _show(self, address: str) -> None:
        self._address, self._status = address, ''
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
