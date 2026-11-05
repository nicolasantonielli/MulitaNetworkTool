"""Daily journal storage contract, independent of filesystem and UI."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class JournalSnapshot:
    days: tuple[str, ...]
    day: str
    revision: str
    # None means the caller already has this revision's text.
    text: str | None
    entries: tuple[dict, ...] | None = None


@dataclass(frozen=True)
class JournalRecord:
    operation_id: str
    timestamp: str
    kind: str
    phase: str
    text: str
    results: str
    lines: tuple[str, ...]


class JournalRepository(Protocol):
    def snapshot(self, day: str, known_day: str = '', known_revision: str = '') -> JournalSnapshot: ...
    def append(self, now: datetime, line: str | JournalRecord) -> None: ...
    def delete(self, day: str) -> None: ...


class JournalFiles(Protocol):
    """Manage a complete stored report without exposing its physical layout."""
    def rename_file(self, source: str, target: str) -> None: ...
    def copy_file(self, source: str, target: str) -> None: ...
    def delete_file(self, name: str) -> None: ...


def technical_line(now: datetime, sentence: str) -> str:
    return f"{now:%Y-%d-%m %H:%M} - {' '.join(sentence.split())}"
