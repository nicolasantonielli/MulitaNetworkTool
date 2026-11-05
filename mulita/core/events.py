"""Technical operation facts, independent of UI, language and persistence."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal
from mulita.core.event_payloads import OperationParameters, OperationResult, RESULT_TYPES, validate_payload
from uuid import uuid4
import logging

EventPhase = Literal['started', 'completed', 'failed', 'stop']

@dataclass(frozen=True)
class OperationEvent:
    action: str
    phase: EventPhase
    parameters: OperationParameters
    result: OperationResult | None = None
    operation_id: str = field(default_factory=lambda: uuid4().hex)
    occurred_at: datetime = field(default_factory=lambda: datetime.now().astimezone())

    def __post_init__(self):
        if not isinstance(self.parameters, OperationParameters):
            raise TypeError('OperationEvent requires OperationParameters')
        validate_payload(self.parameters)
        if self.phase not in ('started', 'completed', 'failed', 'stop'):
            raise ValueError('Invalid operation phase')
        expected = RESULT_TYPES.get(self.action)
        if self.phase == 'completed' and expected is not None and not isinstance(self.result, expected):
            raise TypeError(f'{self.action} completion requires {expected.__name__}')
        if self.result is not None:
            if expected is None or not isinstance(self.result, expected):
                raise TypeError('Result does not match the operation contract')
            validate_payload(self.result)


EventSink = Callable[[OperationEvent], None]


class EventSource:
    """The composition root supplies the observer; operations work without one."""
    _event_sink: EventSink | None = None

    def set_event_sink(self, sink: EventSink) -> None:
        self._event_sink = sink

    def emit_event(self, event: OperationEvent) -> None:
        if self._event_sink is not None:
            try:
                self._event_sink(event)
            except Exception:
                # A reporting failure must never turn a successful network action
                # into a failed action, or prevent delivery of its callback.
                logging.getLogger(__name__).exception('Technical event observer failed')
