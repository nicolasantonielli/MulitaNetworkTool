import queue
import threading
import unittest
from mulita.presentation.dispatcher import UiDispatcher


class Queued(UiDispatcher):
    def __init__(self):
        super().__init__()
        self.calls = queue.Queue()

    def post(self, callback, *args):
        self.calls.put((callback, args))

    def drain(self):
        while not self.calls.empty():
            callback, args = self.calls.get_nowait()
            callback(*args)


class TaskLifecycleTest(unittest.TestCase):
    def test_close_waits_for_write_and_discards_late_ui_callback(self):
        dispatcher = Queued()
        entered, release, closed = threading.Event(), threading.Event(), threading.Event()
        writes, notices = [], []
        def write():
            entered.set()
            release.wait(2)
            writes.append('complete')
        dispatcher.background(write, notices.append)
        self.assertTrue(entered.wait(1))
        closer = threading.Thread(target=lambda: (dispatcher.shutdown(), closed.set()))
        closer.start()
        try:
            self.assertFalse(closed.wait(.05))
        finally:
            release.set()
            closer.join(2)
        dispatcher.drain()
        self.assertTrue(closed.is_set())
        self.assertEqual(writes, ['complete'])
        self.assertEqual(notices, [])

    def test_restart_drains_pending_work_and_rejects_duplicate_requests(self):
        dispatcher = Queued()
        release, restarted = threading.Event(), threading.Event()
        sequence = []
        dispatcher.background(lambda: (release.wait(2), sequence.append('saved')))
        self.assertTrue(dispatcher.finish_background(lambda: (sequence.append('restart'), restarted.set())))
        self.assertFalse(dispatcher.finish_background(lambda: sequence.append('duplicate')))
        self.assertFalse(restarted.wait(.05))
        release.set()
        self.assertTrue(restarted.wait(1))
        dispatcher.shutdown()
        self.assertEqual(sequence, ['saved', 'restart'])

    def test_failed_final_action_reopens_dispatcher(self):
        dispatcher = Queued()
        completed = threading.Event()
        errors = []
        def fail():
            raise OSError('cannot restart')
        dispatcher.finish_background(fail, on_error=errors.append)
        callback, args = dispatcher.calls.get(timeout=1)
        callback(*args)
        dispatcher.background(completed.set)
        self.assertTrue(completed.wait(1))
        dispatcher.shutdown()
        self.assertIsInstance(errors[0], OSError)
