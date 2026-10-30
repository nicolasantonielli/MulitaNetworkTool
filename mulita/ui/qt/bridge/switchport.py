from __future__ import annotations

import json
import os

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.presentation.i18n import tr
from mulita.ui.qt.bridge.base import Controller


class SwitchPortController(Controller):
    changed = pyqtSignal()

    def __init__(self, ctx):
        super().__init__(ctx)
        self._running = False
        self._report = {}
        self._cancelled = self._services.switchport.cancelled
        self._status = ''

    @pyqtProperty(bool, notify=changed)
    def running(self):
        return self._running

    @pyqtProperty(str, notify=changed)
    def reportJson(self):
        return json.dumps(self._report)

    @pyqtProperty(str, notify=changed)
    def status(self):
        return self._status

    @pyqtProperty(bool, constant=True)
    def simulated(self):
        return os.name != 'posix' or bool(self._ctx.config and self._ctx.config.test_mode)

    @pyqtSlot(str, int)
    def start(self, interface, seconds):
        if self._running:
            return
        self._cancelled.clear()
        self._report = {}
        self._running = True
        self._status = tr('switchListening')
        self.changed.emit()
        dispatcher = self._ctx.dispatcher
        dispatcher.background(
            lambda: self._services.switchport.scan(interface, seconds, self._cancelled,
                dispatcher.wrap(self._updated), self.simulated), self._finished, self._failed)

    @pyqtSlot()
    def stop(self):
        self._cancelled.set()
        self._status = tr('switchStopping')
        self.changed.emit()

    @pyqtSlot()
    def clear(self):
        if self._running:
            return
        self._report = {}
        self._status = ''
        self.changed.emit()

    @pyqtSlot()
    def save(self):
        if self._running or not self._report:
            return
        try:
            path = self._services.switchport.save(self._report)
        except OSError as exc:
            self._fail(exc)
            return
        self._ctx.notifier.success(tr('switchTitle'), path.name)

    def _updated(self, report):
        self._report = report
        self.changed.emit()

    def _finished(self, report):
        self._report = report
        self._running = False
        self._status = tr('switchCancelled' if report['cancelled'] else 'switchComplete')
        self.changed.emit()

    def _failed(self, error):
        self._running = False
        self._status = str(error)
        self.changed.emit()
        self._fail(error)
