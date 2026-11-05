"""Independent observer that renders and stores technical operation events."""
import logging
from threading import RLock

from mulita.core.events import OperationEvent
from mulita.core.journals import technical_line


class TechnicalJournalService:
    def __init__(self, settings, render, append):
        self._settings = settings
        self._render = render
        self._append = append
        self._lock = RLock()

    def record(self, event: OperationEvent):
        with self._lock:
            try:
                current = self._settings.current
                if not current.technical_journal:
                    return
                lines = self._render(event, current.language.value)
                for line in lines:
                    self._append(event.occurred_at, technical_line(event.occurred_at, line))
            except Exception:
                logging.getLogger(__name__).exception('Could not write technical journal')
                return
