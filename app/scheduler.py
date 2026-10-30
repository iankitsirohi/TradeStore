"""Background loop that periodically marks matured trades as expired."""
import logging
import threading

logger = logging.getLogger(__name__)


class ExpiryScheduler:
    def __init__(self, task, interval_seconds: float):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self._task = task
        self._interval = interval_seconds
        self._stop = threading.Event()
        self._thread = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="trade-expiry", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while True:
            try:
                self._task()
            except Exception:  # keep the loop alive on transient errors
                logger.exception("trade expiry run failed")
            if self._stop.wait(self._interval):
                break
