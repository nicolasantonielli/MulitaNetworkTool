"""Independent observer that renders and stores technical operation events."""
import logging
from dataclasses import replace
from threading import RLock

from mulita.core.events import OperationEvent
from mulita.core.event_payloads import OperationParameters, ExportReport
from mulita.core.journals import JournalRecord, technical_line
from mulita.core.journal_tests import category


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
                if event.action == 'export_many':
                    # A mixed selection must not leak disabled tests into the report.
                    if event.phase == 'completed':
                        for index, item in enumerate(event.parameters.items):
                            self.record(replace(event, action='export', parameters=OperationParameters(place=item.place),
                                                result=ExportReport((item.name,)), operation_id=f'{event.operation_id}:{index}'))
                    return
                if category(event) not in current.journal_tests:
                    return
                lines = self._render(event, current.language.value)
                if isinstance(lines, JournalRecord):
                    self._append(event.occurred_at, lines)
                    return
                for line in lines:
                    self._append(event.occurred_at, technical_line(event.occurred_at, line))
            except Exception:
                logging.getLogger(__name__).exception('Could not write technical journal')
                return
