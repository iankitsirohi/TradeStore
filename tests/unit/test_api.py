from datetime import timedelta

from app import create_app
from tests.helpers import MutableClock, TODAY, TempDbTestCase, make_payload


class TradeApiTests(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.clock = MutableClock()
        self.app = create_app({"DATABASE_PATH": self.db_path, "TESTING": True}, today_provider=self.clock)
        self.client = self.app.test_client()

    def post(self, **overrides):
        return self.client.post("/trades", json=make_payload(**overrides))

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, response.get_json())

    def test_post_new_trade_returns_201_and_representation(self):
        response = self.post()
        self.assertEqual(201, response.status_code)
        body = response.get_json()
        self.assertEqual("T1", body["trade_id"])
        self.assertEqual(TODAY.isoformat(), body["created_date"])
        self.assertIs(False, body["expired"])

    def test_post_same_version_returns_200(self):
        self.post()
        response = self.post(counter_party_id="CP-2")
        self.assertEqual(200, response.status_code)
        self.assertEqual("CP-2", response.get_json()["counter_party_id"])

    def test_post_lower_version_returns_409(self):
        self.post(version=2)
        response = self.post(version=1)
        self.assertEqual(409, response.status_code)
        self.assertEqual("lower_version", response.get_json()["error"])

    def test_post_past_maturity_returns_422(self):
        response = self.post(maturity_date=(TODAY - timedelta(days=1)).isoformat())
        self.assertEqual(422, response.status_code)
        self.assertEqual("past_maturity_date", response.get_json()["error"])

    def test_post_invalid_payload_returns_422(self):
        response = self.post(version="one")
        self.assertEqual(422, response.status_code)
        self.assertEqual("validation_error", response.get_json()["error"])

    def test_post_without_json_body_returns_422(self):
        response = self.client.post("/trades", data="not json", content_type="text/plain")
        self.assertEqual(422, response.status_code)

    def test_get_latest_version_of_trade(self):
        self.post(version=1)
        self.post(version=2)
        response = self.client.get("/trades/T1")
        self.assertEqual(2, response.get_json()["version"])

    def test_get_unknown_trade_returns_404(self):
        response = self.client.get("/trades/missing")
        self.assertEqual(404, response.status_code)
        self.assertEqual("trade_not_found", response.get_json()["error"])

    def test_get_specific_version_and_all_versions(self):
        self.post(version=1)
        self.post(version=2)
        self.assertEqual(1, self.client.get("/trades/T1/versions/1").get_json()["version"])
        self.assertEqual(404, self.client.get("/trades/T1/versions/7").status_code)
        versions = self.client.get("/trades/T1/versions").get_json()
        self.assertEqual([1, 2], [t["version"] for t in versions])

    def test_list_trades_with_expired_filter(self):
        self.post(trade_id="A", maturity_date=(TODAY + timedelta(days=1)).isoformat())
        self.post(trade_id="B")
        self.clock.advance(2)
        self.assertEqual(2, len(self.client.get("/trades").get_json()))
        expired = self.client.get("/trades?expired=true").get_json()
        self.assertEqual(["A"], [t["trade_id"] for t in expired])
        active = self.client.get("/trades?expired=false").get_json()
        self.assertEqual(["B"], [t["trade_id"] for t in active])

    def test_invalid_expired_filter_returns_422(self):
        self.assertEqual(422, self.client.get("/trades?expired=maybe").status_code)

    def test_manual_expiry_endpoint_reports_count(self):
        self.post(maturity_date=(TODAY + timedelta(days=1)).isoformat())
        self.clock.advance(2)
        response = self.client.post("/trades/expire")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"expired_count": 1}, response.get_json())

    def test_unknown_route_returns_json_404(self):
        response = self.client.get("/nope")
        self.assertEqual(404, response.status_code)
        self.assertEqual("not_found", response.get_json()["error"])

    def test_scheduler_is_started_only_when_requested(self):
        self.assertIsNone(self.app.extensions["expiry_scheduler"])
        app = create_app(
            {"DATABASE_PATH": self.db_path, "EXPIRY_INTERVAL_SECONDS": 3600},
            today_provider=self.clock,
            start_scheduler=True,
        )
        scheduler = app.extensions["expiry_scheduler"]
        self.assertTrue(scheduler.is_running)
        scheduler.stop()
