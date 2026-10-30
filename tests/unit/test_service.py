from datetime import timedelta

from app.exceptions import LowerVersionError, PastMaturityDateError, TradeNotFoundError
from app.repository import TradeRepository
from app.service import TradeService
from tests.helpers import MutableClock, TODAY, TempDbTestCase, make_payload


class TradeServiceTests(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.clock = MutableClock()
        repo = TradeRepository(self.db_path)
        repo.init_schema()
        self.service = TradeService(repo, today=self.clock)

    def test_new_trade_is_stored(self):
        trade, created = self.service.submit_trade(make_payload())
        self.assertTrue(created)
        self.assertEqual(trade, self.service.get_trade("T1"))

    def test_same_version_replaces_existing_record(self):
        self.service.submit_trade(make_payload(counter_party_id="CP-1"))
        trade, created = self.service.submit_trade(make_payload(counter_party_id="CP-2"))
        self.assertFalse(created)
        self.assertEqual("CP-2", self.service.get_trade("T1", 1).counter_party_id)
        self.assertEqual(1, len(self.service.list_trades()))

    def test_higher_version_is_stored_next_to_older_one(self):
        self.service.submit_trade(make_payload(version=1))
        self.service.submit_trade(make_payload(version=2))
        self.assertEqual([1, 2], [t.version for t in self.service.list_versions("T1")])
        self.assertEqual(2, self.service.get_trade("T1").version)

    def test_lower_version_is_rejected_and_store_unchanged(self):
        self.service.submit_trade(make_payload(version=2))
        with self.assertRaises(LowerVersionError):
            self.service.submit_trade(make_payload(version=1))
        self.assertEqual([2], [t.version for t in self.service.list_trades()])

    def test_version_lower_than_latest_but_higher_than_first_is_rejected(self):
        self.service.submit_trade(make_payload(version=1))
        self.service.submit_trade(make_payload(version=3))
        with self.assertRaises(LowerVersionError):
            self.service.submit_trade(make_payload(version=2))

    def test_versions_are_tracked_per_trade_id(self):
        self.service.submit_trade(make_payload(trade_id="T1", version=5))
        self.service.submit_trade(make_payload(trade_id="T2", version=1))
        self.assertEqual(2, len(self.service.list_trades()))

    def test_maturity_in_the_past_is_rejected(self):
        yesterday = (TODAY - timedelta(days=1)).isoformat()
        with self.assertRaises(PastMaturityDateError):
            self.service.submit_trade(make_payload(maturity_date=yesterday))
        self.assertEqual([], self.service.list_trades())

    def test_maturity_today_is_accepted(self):
        self.service.submit_trade(make_payload(maturity_date=TODAY.isoformat()))
        self.assertFalse(self.service.get_trade("T1").expired)

    def test_get_missing_trade_raises(self):
        with self.assertRaises(TradeNotFoundError):
            self.service.get_trade("nope")
        self.service.submit_trade(make_payload())
        with self.assertRaises(TradeNotFoundError):
            self.service.get_trade("T1", 9)
        with self.assertRaises(TradeNotFoundError):
            self.service.list_versions("nope")

    def test_expire_trades_marks_matured_trades(self):
        self.service.submit_trade(make_payload(maturity_date=(TODAY + timedelta(days=2)).isoformat()))
        self.assertEqual(0, self.service.expire_trades())
        self.clock.advance(3)
        self.assertEqual(1, self.service.expire_trades())

    def test_reads_always_reflect_expiry_without_waiting_for_scheduler(self):
        self.service.submit_trade(make_payload(maturity_date=(TODAY + timedelta(days=1)).isoformat()))
        self.clock.advance(2)
        self.assertTrue(self.service.get_trade("T1").expired)
        self.assertTrue(self.service.list_trades()[0].expired)

    def test_list_trades_can_filter_on_expired_flag(self):
        self.service.submit_trade(make_payload(trade_id="A", maturity_date=(TODAY + timedelta(days=1)).isoformat()))
        self.service.submit_trade(make_payload(trade_id="B"))
        self.clock.advance(2)
        self.assertEqual(["A"], [t.trade_id for t in self.service.list_trades(expired=True)])
        self.assertEqual(["B"], [t.trade_id for t in self.service.list_trades(expired=False)])

    def test_resubmitting_same_version_with_future_maturity_clears_expired_flag(self):
        self.service.submit_trade(make_payload(maturity_date=(TODAY + timedelta(days=1)).isoformat()))
        self.clock.advance(2)
        self.service.expire_trades()
        self.service.submit_trade(make_payload(maturity_date=(self.clock.today + timedelta(days=9)).isoformat()))
        self.assertFalse(self.service.get_trade("T1").expired)
