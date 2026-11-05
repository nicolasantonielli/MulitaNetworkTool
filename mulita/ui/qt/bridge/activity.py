"""Registro diario de acciones iniciadas desde Mulita."""
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.presentation.i18n import Translator
from mulita.servers.activity_days import append_entry, day_path, list_days, technical_line
from mulita.ui.qt.bridge.base import Controller


class DailyJournal(Controller):
    changed = pyqtSignal()

    def __init__(self, ctx, place, suffix):
        super().__init__(ctx)
        self._folder = Path(ctx.config.storage.folder(place))
        self.suffix = suffix

    def _append(self, now, line):
        try:
            append_entry(self._folder, now, self.suffix, line)
        except (OSError, ValueError) as error:
            self._fail(error)
            return
        self.changed.emit()

    @pyqtProperty('QStringList', notify=changed)
    def days(self):
        try:
            return list_days(self._folder, self.suffix)
        except (OSError, ValueError) as error:
            self._fail(error)
            return []

    @pyqtSlot(str, result=str)
    def revision(self, day):
        try:
            stat = day_path(self._folder, day, self.suffix).stat()
            return f'{stat.st_mtime_ns}:{stat.st_size}'
        except (OSError, ValueError):
            return ''

    @pyqtSlot(str, result=str)
    def read(self, day):
        if not day:
            return ''
        try:
            path = day_path(self._folder, day, self.suffix)
            return path.read_text(encoding='utf-8')
        except FileNotFoundError:
            return ''
        except (OSError, ValueError) as error:
            self._fail(error)
            return ''

    @pyqtSlot(str)
    def deleteDay(self, day):
        try:
            day_path(self._folder, day, self.suffix).unlink(missing_ok=True)
        except (OSError, ValueError) as error:
            self._fail(error)
        self.changed.emit()


class ActivityController(DailyJournal):
    def __init__(self, ctx):
        super().__init__(ctx, 'actividad', '.log')
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
        self._append(now, line)


class TechnicalJournal(DailyJournal):
    def __init__(self, ctx):
        super().__init__(ctx, 'bitacora', '.txt')

    def note(self, sentence):
        if self._ctx.settings.current.technical_journal:
            now = datetime.now().astimezone()
            self._append(now, technical_line(now, sentence))

    def action(self, key, detail, phase):
        if not self._ctx.settings.current.technical_journal:
            return
        label = Translator('es').tr(key)
        subject = f'{label} ({detail})' if detail else label
        if phase == 'activityFailed':
            self.note(f'Falló la operación «{subject}».')
        elif phase == 'activityStop':
            self.note(f'Se solicitó detener «{subject}».')
        elif phase == 'activityStarted':
            if key == 'pingTitle':
                self.note(f'Se hizo ping a {detail}.')
            elif key == 'tracesTitle':
                self.note(f'Se trazó la ruta hasta {detail}.')
            elif key == 'captureTitle':
                self.note(f'Se inició una captura en la interfaz {detail}.')
            elif key not in ('export', 'save'):
                self.note(f'Se inició la operación «{subject}».')
        elif phase == 'activityCompleted' and key == 'connect':
            self.note(f'Se estableció la conexión Wi-Fi con la red {detail}.')
        elif phase == 'activityCompleted' and key == 'wifiDisconnect':
            self.note('Se desconectó la interfaz Wi-Fi.')
        elif phase in ('activityCompleted', 'activityEnded') and key not in (
                'pingTitle', 'tracesTitle', 'discoverTitle', 'scanPorts', 'toolSpeed',
                'publicIp', 'vendor', 'cyberTls', 'cyberNmap', 'export', 'save'):
            self.note(f'Finalizó la operación «{subject}».')
