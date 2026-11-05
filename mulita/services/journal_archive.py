"""Ordered background access to a journal repository, usable without Qt."""
from concurrent.futures import ThreadPoolExecutor
import logging
from threading import RLock

from mulita.core.journals import JournalRepository


class JournalArchive:
    def __init__(self, repository: JournalRepository):
        self._repository = repository
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='mulita-journal')
        self._lock = RLock()
        self._listeners = []

    def subscribe(self, changed, failed):
        pair = (changed, failed)
        with self._lock:
            self._listeners.append(pair)
        def unsubscribe():
            with self._lock:
                if pair in self._listeners:
                    self._listeners.remove(pair)
        return unsubscribe

    def snapshot(self, day, known_day='', known_revision=''):
        return self._worker.submit(self._repository.snapshot, day, known_day, known_revision)

    def _mutate(self, action, *args):
        def work():
            try:
                action(*args)
            except Exception as error:
                logging.getLogger(__name__).exception('Could not update journal')
                self._notify(error)
                raise
            self._notify()
        return self._worker.submit(work)

    def _notify(self, error=None):
        with self._lock:
            listeners = tuple(self._listeners)
        for changed, failed in listeners:
            try:
                failed(error) if error is not None else changed()
            except Exception:
                logging.getLogger(__name__).exception('Journal listener failed')

    def append(self, now, line):
        return self._mutate(self._repository.append, now, line)

    def delete(self, day):
        return self._mutate(self._repository.delete, day)

    def flush(self):
        """Barrier for export/shutdown workers; never call on the UI thread."""
        self._worker.submit(lambda: None).result()

    def close(self):
        self._worker.shutdown(wait=True)
