import threading
import unittest

from app.scheduler import ExpiryScheduler


class ExpirySchedulerTests(unittest.TestCase):
    def test_task_runs_repeatedly_until_stopped(self):
        done = threading.Event()
        calls = []

        def task():
            calls.append(1)
            if len(calls) >= 3:
                done.set()

        scheduler = ExpiryScheduler(task, interval_seconds=0.01)
        scheduler.start()
        self.assertTrue(done.wait(timeout=5))
        scheduler.stop()
        self.assertFalse(scheduler.is_running)

    def test_task_failure_does_not_kill_the_scheduler(self):
        done = threading.Event()
        calls = []

        def task():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("transient failure")
            done.set()

        scheduler = ExpiryScheduler(task, interval_seconds=0.01)
        with self.assertLogs("app.scheduler", level="ERROR"):
            scheduler.start()
            self.assertTrue(done.wait(timeout=5))
        scheduler.stop()

    def test_start_twice_does_not_spawn_second_thread(self):
        scheduler = ExpiryScheduler(lambda: None, interval_seconds=0.01)
        scheduler.start()
        first = scheduler._thread
        scheduler.start()
        self.assertIs(first, scheduler._thread)
        scheduler.stop()

    def test_stop_without_start_is_safe(self):
        ExpiryScheduler(lambda: None, interval_seconds=1).stop()

    def test_non_positive_interval_is_rejected(self):
        with self.assertRaises(ValueError):
            ExpiryScheduler(lambda: None, interval_seconds=0)
