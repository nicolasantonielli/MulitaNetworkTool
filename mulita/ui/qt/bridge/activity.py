"""Registro diario de acciones iniciadas desde Mulita."""
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.servers.activity_days import day_path, list_days
from mulita.ui.qt.bridge.base import Controller


class ActivityController(Controller):
    changed = pyqtSignal()

    def __init__(self, ctx):
        super().__init__(ctx)
        self._folder = Path(ctx.config.storage.folder('actividad'))
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
        if not self._ctx.settings.current.activity_logging:
            return
        now = datetime.now().astimezone()
        # Una acción ocupa una línea, incluso si el operador pegó texto multilínea.
        parts = (now.isoformat(timespec='seconds'), self._tr(action), detail,
                 self._tr(phase) if phase else '')
        line = ' | '.join(' '.join(str(part).split())[:512] for part in parts if part)
        try:
            self._folder.mkdir(parents=True, exist_ok=True)
            with day_path(self._folder, now.date().isoformat()).open('a', encoding='utf-8') as stream:
                stream.write(line + '\n')
        except (OSError, ValueError) as error:
            self._fail(error)
            return
        self.changed.emit()

    @pyqtProperty('QStringList', notify=changed)
    def days(self):
        try:
            return list_days(self._folder)
        except (OSError, ValueError) as error:
            self._fail(error)
            return []

    @pyqtSlot(str, result=str)
    def read(self, day):
        if not day:
            return ''
        try:
            path = day_path(self._folder, day)
            return path.read_text(encoding='utf-8')
        except FileNotFoundError:
            return ''
        except (OSError, ValueError) as error:
            self._fail(error)
            return ''

    @pyqtSlot(str)
    def deleteDay(self, day):
        try:
            day_path(self._folder, day).unlink(missing_ok=True)
        except (OSError, ValueError) as error:
            self._fail(error)
        self.changed.emit()
