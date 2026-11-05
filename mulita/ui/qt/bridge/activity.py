"""Qt presentation of daily journals. All file operations run in archive workers."""
from datetime import datetime

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.ui.qt.bridge.base import Controller


class DailyJournal(Controller):
    changed = pyqtSignal()
    busyChanged = pyqtSignal()
    invalidated = pyqtSignal()

    def __init__(self, ctx, archive):
        super().__init__(ctx)
        self._archive = archive
        self._days = []
        self._entries = []
        self._day = self._report = self._revision = self._desired_day = ''
        self._loading = self._deleting = self._refresh_pending = self._closed = False
        self._generation = 0
        self._unsubscribe = archive.subscribe(
            ctx.dispatcher.wrap(self._invalidated), ctx.dispatcher.wrap(self._write_failed))

    def _invalidated(self):
        if not self._closed:
            self.invalidated.emit()

    def _write_failed(self, error):
        if not self._closed:
            self._fail(error)

    @pyqtProperty(bool, notify=busyChanged)
    def busy(self):
        return self._loading or self._deleting

    @pyqtProperty('QStringList', notify=changed)
    def days(self):
        return list(self._days)

    @pyqtProperty(str, notify=changed)
    def day(self):
        return self._day

    @pyqtProperty(str, notify=changed)
    def report(self):
        return self._report

    @pyqtProperty('QVariantList', notify=changed)
    def entries(self):
        return list(self._entries)

    @pyqtSlot(str, result=str)
    def revision(self, day):
        return self._revision if day == self._day else ''

    @pyqtSlot(str, result=str)
    def read(self, day):
        return self._report if day == self._day else ''

    def _observe(self, future, success, failure):
        ok = self._ctx.dispatcher.wrap(success)
        fail = self._ctx.dispatcher.wrap(failure)
        def finished(result):
            try:
                value = result.result()
            except Exception as error:
                fail(error)
            else:
                ok(value)
        future.add_done_callback(finished)

    @pyqtSlot(str)
    def refresh(self, day):
        if self._closed:
            return
        if day != self._desired_day:
            self._desired_day = day
            self._generation += 1
        if self.busy:
            self._refresh_pending = True
            return
        self._load()

    def _load(self):
        self._refresh_pending = False
        self._loading = True
        self.busyChanged.emit()
        generation = self._generation
        future = self._archive.snapshot(self._desired_day, self._day, self._revision)
        self._observe(future, lambda snapshot: self._loaded(generation, snapshot),
                      lambda error: self._loaded(generation, None, error))

    def _loaded(self, generation, snapshot, error=None):
        if self._closed:
            return
        self._loading = False
        if generation == self._generation:
            if error is not None:
                self._fail(error)
            else:
                self._days = list(snapshot.days)
                self._day = self._desired_day = snapshot.day
                self._revision = snapshot.revision
                if snapshot.text is not None:
                    self._report = snapshot.text
                    self._entries = list(snapshot.entries or ())
                self.changed.emit()
        self.busyChanged.emit()
        if self._refresh_pending and not self._deleting:
            self._load()

    @pyqtSlot(str)
    def deleteDay(self, day):
        if self._closed or self._deleting:
            return
        self._generation += 1
        self._deleting = self._refresh_pending = True
        self.busyChanged.emit()
        # Archive notifications report write errors once; completion refreshes
        # the snapshot whether deletion succeeded or the file is still present.
        self._observe(self._archive.delete(day), self._deleted, self._deleted)

    def _deleted(self, _result):
        if self._closed:
            return
        self._deleting = False
        self._refresh_pending = True
        self.busyChanged.emit()
        if not self._loading:
            self._load()

    def close(self):
        self._closed = True
        self._generation += 1
        self._unsubscribe()


class ActivityController(DailyJournal):
    def __init__(self, ctx, archive):
        super().__init__(ctx, archive)
        self._previous = ctx.settings.current
        ctx.settings.subscribe(self._settings_changed)

    def _settings_changed(self, current):
        previous = self._previous
        self._previous = current
        if not current.activity_logging:
            return
        if not previous.activity_logging:
            self.record('activityOn')
        values = (
            ('language', previous.language.value, current.language.value),
            ('theme', previous.theme.value, current.theme.value),
            ('brightness', previous.brightness, current.brightness),
            ('rotation', previous.display.rotation, current.display.rotation),
            ('resizeTiles', previous.display.resize_tiles, current.display.resize_tiles),
            ('scale', previous.display.ui_scale, current.display.ui_scale),
        )
        for action, before, after in values:
            if before != after:
                self.record(action, f'{before} → {after}')
        if previous.home != current.home:
            self.record('tileOrderTitle', phase='activityCompleted')

    def record(self, action: str, detail: str = '', phase: str = '') -> None:
        if self._closed or not self._ctx.settings.current.activity_logging:
            return
        now = datetime.now().astimezone()
        # Una acción ocupa una línea, incluso si el operador pegó texto multilínea.
        parts = (now.isoformat(timespec='seconds'), self._tr(action), detail,
                 self._tr(phase) if phase else '')
        line = ' | '.join(' '.join(str(part).split())[:512] for part in parts if part)
        self._archive.append(now, line)


class TechnicalJournal(DailyJournal):
    """The shared archive supplies snapshots; recording belongs to services."""
    pass
