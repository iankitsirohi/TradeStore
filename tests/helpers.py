"""Shared helpers for the test-suite."""
import os
import shutil
import tempfile
import unittest
from datetime import date, timedelta

TODAY = date(2026, 10, 30)


class MutableClock:
    """A controllable replacement for ``date.today`` so time can be moved in tests."""

    def __init__(self, today=TODAY):
        self.today = today

    def __call__(self):
        return self.today

    def advance(self, days):
        self.today += timedelta(days=days)


def make_payload(**overrides):
    payload = {
        "trade_id": "T1",
        "version": 1,
        "counter_party_id": "CP-1",
        "portfolio_id": "B1",
        "maturity_date": (TODAY + timedelta(days=30)).isoformat(),
    }
    payload.update(overrides)
    return payload


class TempDbTestCase(unittest.TestCase):
    """Gives every test its own throw-away SQLite file."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self._tmp, "trades.db")
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
