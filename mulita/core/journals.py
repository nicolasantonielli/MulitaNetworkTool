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


class JournalRepository(Protocol):
    def snapshot(self, day: str, known_day: str = '', known_revision: str = '') -> JournalSnapshot: ...
    def append(self, now: datetime, line: str) -> None: ...
    def delete(self, day: str) -> None: ...


def technical_line(now: datetime, sentence: str) -> str:
    return f"{now:%Y-%d-%m %H:%M} - {' '.join(sentence.split())}"
