"""Filesystem implementation of daily journals. Called only by archive workers."""
import os
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from mulita.core.journals import JournalSnapshot, JournalRecord
from mulita.core.journal_entries import entries_from, journal_csv
from mulita.adapters.journal_lock import journal_lock
from mulita.adapters.journal_files import append_entry, day_path, list_days
from mulita.core.errors import ValidationError
from mulita.core.messages import message


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

    def read_entries(self, day):
        with self.transaction():
            text = day_path(self._folder, day, self._suffix).read_text(encoding='utf-8')
            return entries_from(text, self._metadata(day))

    def csv_bytes(self, day):
        return journal_csv(self.read_entries(day))

    def _metadata(self, day):
        if self._suffix != '.txt':
            return ''
        try:
            return day_path(self._folder, day, '.jsonl').read_text(encoding='utf-8')
        except (FileNotFoundError, UnicodeDecodeError):
            return ''

    def _snapshot(self, day, known_day='', known_revision=''):
        days = list_days(self._folder, self._suffix)
        # Another process may delete a day between listing and opening it.
        while days:
            selected = day if day in days else days[0]
            try:
                with day_path(self._folder, selected, self._suffix).open('r', encoding='utf-8') as stream:
                    stat = os.fstat(stream.fileno())
                    revision = f'{stat.st_dev}:{stat.st_ino}:{stat.st_mtime_ns}:{stat.st_size}'
                    if self._suffix == '.txt':
                        metadata_path = day_path(self._folder, selected, '.jsonl')
                        if metadata_path.exists():
                            meta_stat = metadata_path.stat()
                            revision += f':{meta_stat.st_mtime_ns}:{meta_stat.st_size}'
                    text = None if selected == known_day and revision == known_revision else stream.read()
                    entries = entries_from(text, self._metadata(selected)) if text is not None and self._suffix == '.txt' else None
                    return JournalSnapshot(tuple(days), selected, revision, text, entries)
            except FileNotFoundError:
                days.remove(selected)
        return JournalSnapshot((), '', '', '', ())

    def append(self, now, line):
        with self.transaction():
            if isinstance(line, JournalRecord):
                for sentence in line.lines:
                    append_entry(self._folder, now, self._suffix, sentence)
                append_entry(self._folder, now, '.jsonl', json.dumps(asdict(line), ensure_ascii=False))
            else:
                append_entry(self._folder, now, self._suffix, line)

    def delete(self, day, *, missing_ok=True):
        with self.transaction():
            path = day_path(self._folder, day, self._suffix)
            self._delete_file(path.name, missing_ok=missing_ok)

    def _parts(self, name):
        path = self._folder / name
        if Path(name).name != name or path.suffix != self._suffix or self._folder.is_symlink():
            raise ValidationError(message('badStoredName'))
        parts = (path, path.with_suffix('.jsonl')) if self._suffix == '.txt' else (path,)
        if any(part.is_symlink() or (part.exists() and not part.is_file()) for part in parts):
            raise ValidationError(message('badStoredName'))
        return parts

    def _delete_file(self, name, missing_ok=False):
        parts = self._parts(name)
        parts[0].unlink(missing_ok=missing_ok)
        for part in parts[1:]:
            part.unlink(missing_ok=True)

    def delete_file(self, name):
        with self.transaction():
            self._delete_file(name)

    def rename_file(self, source, target):
        self._transfer(source, target, move=True)

    def copy_file(self, source, target):
        self._transfer(source, target, move=False)

    def _transfer(self, source, target, *, move):
        with self.transaction():
            sources, targets = self._parts(source), self._parts(target)
            if not sources[0].is_file():
                raise ValidationError(message('fileMissing'))
            if move and source == target:
                return
            if any(path.exists() for path in targets):
                raise ValidationError(message('nameExists'))
            completed = []
            try:
                for src, dst in zip(sources, targets):
                    if src.exists():
                        completed.append((src, dst))
                        src.rename(dst) if move else shutil.copyfile(src, dst)
            except OSError:
                for src, dst in reversed(completed):
                    if dst.exists():
                        dst.rename(src) if move else dst.unlink()
                raise
