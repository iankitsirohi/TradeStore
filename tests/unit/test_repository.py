from datetime import date

from app.models import Trade
from app.repository import TradeRepository
from tests.helpers import TempDbTestCase


def trade(trade_id="T1", version=1, maturity=date(2027, 1, 1), cp="CP-1", expired=False):
    return Trade(trade_id, version, cp, "B1", maturity, date(2026, 10, 30), expired)


class TradeRepositoryTests(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.repo = TradeRepository(self.db_path)
        self.repo.init_schema()

    def _upsert(self, t):
        with self.repo.transaction() as conn:
            return self.repo.upsert(conn, t)

    def test_init_schema_is_idempotent(self):
        self.repo.init_schema()
        self.assertEqual([], self.repo.list_all())

    def test_insert_returns_false_and_trade_can_be_read_back(self):
        self.assertFalse(self._upsert(trade()))
        self.assertEqual(trade(), self.repo.get("T1", 1))

    def test_same_key_replaces_and_returns_true(self):
        self._upsert(trade(cp="CP-1"))
        self.assertTrue(self._upsert(trade(cp="CP-9")))
        self.assertEqual("CP-9", self.repo.get("T1", 1).counter_party_id)
        self.assertEqual(1, len(self.repo.list_all()))

    def test_max_version(self):
        with self.repo.transaction() as conn:
            self.assertIsNone(self.repo.max_version(conn, "T1"))
        for v in (1, 3, 2):
            self._upsert(trade(version=v))
        with self.repo.transaction() as conn:
            self.assertEqual(3, self.repo.max_version(conn, "T1"))

    def test_get_without_version_returns_latest(self):
        for v in (1, 2):
            self._upsert(trade(version=v))
        self.assertEqual(2, self.repo.get("T1").version)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.repo.get("nope"))
        self.assertIsNone(self.repo.get("nope", 1))

    def test_list_all_and_versions_are_ordered(self):
        self._upsert(trade("T2", 2))
        self._upsert(trade("T1", 1))
        self._upsert(trade("T2", 1))
        keys = [(t.trade_id, t.version) for t in self.repo.list_all()]
        self.assertEqual([("T1", 1), ("T2", 1), ("T2", 2)], keys)
        self.assertEqual([1, 2], [t.version for t in self.repo.list_versions("T2")])

    def test_expire_before_marks_only_matured_trades(self):
        self._upsert(trade("OLD", maturity=date(2026, 10, 29)))
        self._upsert(trade("TODAY", maturity=date(2026, 10, 30)))
        self._upsert(trade("NEW", maturity=date(2027, 1, 1)))
        self.assertEqual(1, self.repo.expire_before(date(2026, 10, 30)))
        self.assertTrue(self.repo.get("OLD").expired)
        self.assertFalse(self.repo.get("TODAY").expired)
        self.assertFalse(self.repo.get("NEW").expired)

    def test_expire_before_is_idempotent(self):
        self._upsert(trade(maturity=date(2020, 1, 1)))
        self.assertEqual(1, self.repo.expire_before(date(2026, 10, 30)))
        self.assertEqual(0, self.repo.expire_before(date(2026, 10, 30)))

    def test_transaction_rolls_back_on_error(self):
        with self.assertRaises(RuntimeError):
            with self.repo.transaction() as conn:
                self.repo.upsert(conn, trade())
                raise RuntimeError("boom")
        self.assertEqual([], self.repo.list_all())
