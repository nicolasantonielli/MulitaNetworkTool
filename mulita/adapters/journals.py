"""Filesystem implementation of daily journals. Called only by archive workers."""
import os
from pathlib import Path

from mulita.core.journals import JournalSnapshot
from mulita.adapters.journal_lock import journal_lock
from mulita.servers.activity_days import append_entry, day_path, list_days


class FileJournalRepository:
    def __init__(self, folder: Path, suffix: str):
        self._folder = folder
        self._suffix = suffix

    def snapshot(self, day, known_day='', known_revision=''):
        with self.transaction():
            return self._snapshot(day, known_day, known_revision)

    def transaction(self):
        return journal_lock(self._folder)

    def days(self):
        with self.transaction():
            return list_days(self._folder, self._suffix)

    def read_bytes(self, day):
        """A complete snapshot. Do not hold the lock while sending it to a client."""
        with self.transaction():
            return day_path(self._folder, day, self._suffix).read_bytes()

    def _snapshot(self, day, known_day='', known_revision=''):
        days = list_days(self._folder, self._suffix)
        # Another process may delete a day between listing and opening it.
        while days:
            selected = day if day in days else days[0]
            try:
                with day_path(self._folder, selected, self._suffix).open('r', encoding='utf-8') as stream:
                    stat = os.fstat(stream.fileno())
                    revision = f'{stat.st_dev}:{stat.st_ino}:{stat.st_mtime_ns}:{stat.st_size}'
                    text = None if selected == known_day and revision == known_revision else stream.read()
                    return JournalSnapshot(tuple(days), selected, revision, text)
            except FileNotFoundError:
                days.remove(selected)
        return JournalSnapshot((), '', '', '')

    def append(self, now, line):
        with self.transaction():
            append_entry(self._folder, now, self._suffix, line)

    def delete(self, day, *, missing_ok=True):
        with self.transaction():
            day_path(self._folder, day, self._suffix).unlink(missing_ok=missing_ok)
