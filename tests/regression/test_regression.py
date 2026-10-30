"""End-to-end regression scenarios taken from the problem statement.

They go through the HTTP layer only, so any behavioural change that breaks
the contract of the trade store is caught here.
"""
from datetime import date, timedelta

from app import create_app
from tests.helpers import MutableClock, TempDbTestCase


class ProblemStatementRegressionTests(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.clock = MutableClock(date(2026, 10, 30))
        app = create_app({"DATABASE_PATH": self.db_path}, today_provider=self.clock)
        self.client = app.test_client()

    def send(self, trade_id, version, cp, portfolio, maturity, created=None):
        body = {
            "trade_id": trade_id, "version": version, "counter_party_id": cp,
            "portfolio_id": portfolio, "maturity_date": maturity,
        }
        if created:
            body["created_date"] = created
        return self.client.post("/trades", json=body)

    def test_table_from_the_problem_statement(self):
        self.assertEqual(201, self.send("T1", 1, "CP-1", "B1", "20/05/2027").status_code)
        self.assertEqual(201, self.send("T2", 2, "CP-2", "B1", "20/05/2027").status_code)
        # older version of T2 arrives late -> rejected
        late = self.send("T2", 1, "CP-1", "B1", "20/05/2027", created="14/03/2015")
        self.assertEqual(409, late.status_code)
        # T3 has a maturity date in the past -> rejected
        self.assertEqual(422, self.send("T3", 3, "CP-3", "B2", "20/05/2014").status_code)

        stored = {(t["trade_id"], t["version"]) for t in self.client.get("/trades").get_json()}
        self.assertEqual({("T1", 1), ("T2", 2)}, stored)

    def test_same_version_replaces_the_record(self):
        self.send("T1", 1, "CP-1", "B1", "20/05/2027")
        response = self.send("T1", 1, "CP-9", "B7", "20/06/2027")
        self.assertEqual(200, response.status_code)
        trade = self.client.get("/trades/T1").get_json()
        self.assertEqual(("CP-9", "B7"), (trade["counter_party_id"], trade["portfolio_id"]))
        self.assertEqual(1, len(self.client.get("/trades").get_json()))

    def test_trade_is_expired_automatically_once_maturity_passes(self):
        maturity = (self.clock.today + timedelta(days=5)).isoformat()
        self.send("T1", 1, "CP-1", "B1", maturity)
        self.assertFalse(self.client.get("/trades/T1").get_json()["expired"])
        self.clock.advance(5)  # maturity day itself: still live
        self.assertFalse(self.client.get("/trades/T1").get_json()["expired"])
        self.clock.advance(1)  # day after maturity
        self.assertTrue(self.client.get("/trades/T1").get_json()["expired"])

    def test_multiple_versions_are_retained_and_latest_is_served(self):
        self.send("T2", 1, "CP-1", "B1", "20/05/2027")
        self.send("T2", 2, "CP-2", "B1", "20/05/2027")
        self.assertEqual(2, self.client.get("/trades/T2").get_json()["version"])
        self.assertEqual(2, len(self.client.get("/trades/T2/versions").get_json()))
