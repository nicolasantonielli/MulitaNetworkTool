"""Stable, process-shared advisory lock for one daily journal directory."""
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import threading
import time

_guard = threading.Lock()
_locks = {}


@contextmanager
def journal_lock(folder: Path):
    # Keep the lock outside the daily files: deleting a day must not replace
    # the inode/handle on which another process is waiting.
    folder = folder.absolute()
    if folder.is_symlink():
        raise ValueError('Ruta de registro inválida')
    folder.parent.mkdir(parents=True, exist_ok=True)
    path = folder.parent / ('.mulita-' + folder.name + '.lock')
    if path.is_symlink():
        raise ValueError('Ruta de bloqueo inválida')
    with _guard:
        local = _locks.setdefault(os.path.normcase(str(path.resolve())), threading.Lock())
    with local, path.open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b'\0')
                stream.flush()
            while True:
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    time.sleep(.01)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
