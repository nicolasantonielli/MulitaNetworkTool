"""Real independent processes exercise the same lock used by Qt and HTTP."""
from datetime import datetime
import multiprocessing
from pathlib import Path
import tempfile
import unittest

from mulita.adapters.journals import FileJournalRepository

DAY = '2026-11-05'
NOW = datetime(2026, 11, 5, 12, 30)


def append_worker(folder, gate, marker):
    repository = FileJournalRepository(Path(folder), '.txt')
    gate.wait(10)
    for number in range(20):
        repository.append(NOW, f'{marker}:{number}:' + 'á' * 8192)


def hold_worker(folder, entered, release, split_write):
    repository = FileJournalRepository(Path(folder), '.txt')
    with repository.transaction():
        if split_write:
            with (Path(folder) / (DAY + '.txt')).open('w', encoding='utf-8', newline='\n') as stream:
                stream.write('first-')
                stream.flush()
                entered.set()
                release.wait(10)
                stream.write('last\n')
        else:
            entered.set()
            release.wait(10)


def access_worker(folder, operation, started, done, results):
    repository = FileJournalRepository(Path(folder), '.txt')
    started.set()
    if operation == 'read':
        results.put(repository.read_bytes(DAY))
    else:
        repository.delete(DAY)
    done.set()


class JournalConcurrencyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / 'bitacora'
        self.folder.mkdir()
        self.ctx = multiprocessing.get_context('spawn')
        self.processes = []

    def tearDown(self):
        for process in self.processes:
            if process.is_alive():
                process.terminate()
            process.join(5)
        self.tmp.cleanup()

    def spawn(self, target, *args):
        process = self.ctx.Process(target=target, args=(str(self.folder), *args))
        self.processes.append(process)
        process.start()
        return process

    def joined(self, process):
        process.join(10)
        self.assertEqual(process.exitcode, 0)

    def test_concurrent_process_writes_and_snapshots_keep_complete_utf8_lines(self):
        gate = self.ctx.Event()
        first = self.spawn(append_worker, gate, 'qt')
        second = self.spawn(append_worker, gate, 'web')
        repository = FileJournalRepository(self.folder, '.txt')
        gate.set()
        for _ in range(15):
            snapshot = repository.snapshot(DAY)
            for line in (snapshot.text or '').splitlines():
                marker, number, payload = line.split(':')
                self.assertIn(marker, ('qt', 'web'))
                self.assertTrue(number.isdigit())
                self.assertEqual(payload, 'á' * 8192)
        self.joined(first)
        self.joined(second)
        lines = repository.read_bytes(DAY).decode('utf-8').splitlines()
        self.assertEqual(len(lines), 40)
        self.assertEqual(set(lines), {f'{marker}:{number}:' + 'á' * 8192
                                     for marker in ('qt', 'web') for number in range(20)})

    def test_read_and_delete_wait_for_another_process_to_finish_writing(self):
        for operation in ('read', 'delete'):
            with self.subTest(operation=operation):
                entered, release = self.ctx.Event(), self.ctx.Event()
                started, done = self.ctx.Event(), self.ctx.Event()
                results = self.ctx.Queue()
                holder = self.spawn(hold_worker, entered, release, True)
                self.assertTrue(entered.wait(5))
                accessor = self.spawn(access_worker, operation, started, done, results)
                self.assertTrue(started.wait(5))
                self.assertFalse(done.wait(.1))
                self.assertTrue((self.folder / (DAY + '.txt')).exists())
                release.set()
                self.joined(holder)
                self.joined(accessor)
                if operation == 'read':
                    self.assertEqual(results.get(timeout=2), b'first-last\n')
                else:
                    self.assertFalse((self.folder / (DAY + '.txt')).exists())
                    # Deletion removes committed history; subsequent activity
                    # can create the day's file again, using the same lock.
                    repository = FileJournalRepository(self.folder, '.txt')
                    repository.append(NOW, 'new operation')
                    self.assertEqual(repository.read_bytes(DAY).splitlines(), [b'new operation'])
                results.close()

    def test_process_exit_releases_lock_without_deleting_the_lock_file(self):
        repository = FileJournalRepository(self.folder, '.txt')
        repository.append(NOW, 'kept')
        entered, release = self.ctx.Event(), self.ctx.Event()
        holder = self.spawn(hold_worker, entered, release, False)
        self.assertTrue(entered.wait(5))
        holder.terminate()
        holder.join(5)
        started, done, results = self.ctx.Event(), self.ctx.Event(), self.ctx.Queue()
        reader = self.spawn(access_worker, 'read', started, done, results)
        self.joined(reader)
        self.assertEqual(results.get(timeout=2).splitlines(), [b'kept'])
        self.assertTrue((self.folder.parent / '.mulita-bitacora.lock').exists())
        results.close()
