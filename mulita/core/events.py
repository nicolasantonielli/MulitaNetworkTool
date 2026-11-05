"""Technical operation facts, independent of UI, language and persistence."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping
from types import MappingProxyType
from uuid import uuid4
import logging


@dataclass(frozen=True)
class OperationEvent:
    action: str
    phase: str
    parameters: Mapping[str, Any]
    result: Any = None
    operation_id: str = field(default_factory=lambda: uuid4().hex)
    occurred_at: datetime = field(default_factory=lambda: datetime.now().astimezone())

    def __post_init__(self):
        object.__setattr__(self, 'parameters', MappingProxyType(dict(self.parameters)))


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
