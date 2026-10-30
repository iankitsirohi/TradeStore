import unittest
from datetime import date, timedelta

from app.exceptions import ValidationError
from app.validation import parse_trade
from tests.helpers import TODAY, make_payload


class ParseTradeTests(unittest.TestCase):
    def test_valid_payload_is_converted_to_trade(self):
        trade = parse_trade(make_payload(), TODAY)
        self.assertEqual("T1", trade.trade_id)
        self.assertEqual(1, trade.version)
        self.assertEqual("CP-1", trade.counter_party_id)
        self.assertEqual("B1", trade.portfolio_id)
        self.assertEqual(TODAY + timedelta(days=30), trade.maturity_date)
        self.assertFalse(trade.expired)

    def test_created_date_defaults_to_today(self):
        self.assertEqual(TODAY, parse_trade(make_payload(), TODAY).created_date)

    def test_explicit_created_date_is_kept(self):
        trade = parse_trade(make_payload(created_date="2015-03-14"), TODAY)
        self.assertEqual(date(2015, 3, 14), trade.created_date)

    def test_future_created_date_is_rejected(self):
        future = (TODAY + timedelta(days=1)).isoformat()
        with self.assertRaises(ValidationError):
            parse_trade(make_payload(created_date=future), TODAY)

    def test_day_month_year_format_is_accepted(self):
        trade = parse_trade(make_payload(maturity_date="20/05/2027"), TODAY)
        self.assertEqual(date(2027, 5, 20), trade.maturity_date)

    def test_client_cannot_set_expired_flag(self):
        self.assertFalse(parse_trade(make_payload(expired=True), TODAY).expired)

    def test_missing_required_fields_are_rejected(self):
        for field in ("trade_id", "version", "counter_party_id", "portfolio_id", "maturity_date"):
            with self.subTest(field=field):
                payload = make_payload()
                del payload[field]
                with self.assertRaises(ValidationError) as ctx:
                    parse_trade(payload, TODAY)
                self.assertIn(field, str(ctx.exception))

    def test_blank_strings_are_rejected(self):
        for field in ("trade_id", "counter_party_id", "portfolio_id"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                parse_trade(make_payload(**{field: "   "}), TODAY)

    def test_overlong_identifier_is_rejected(self):
        with self.assertRaises(ValidationError):
            parse_trade(make_payload(trade_id="x" * 65), TODAY)

    def test_non_string_identifier_is_rejected(self):
        with self.assertRaises(ValidationError):
            parse_trade(make_payload(trade_id=123), TODAY)

    def test_invalid_versions_are_rejected(self):
        for bad in ("1", True, 0, -1, 1.5, None):
            with self.subTest(version=bad), self.assertRaises(ValidationError):
                parse_trade(make_payload(version=bad), TODAY)

    def test_invalid_dates_are_rejected(self):
        for bad in ("not-a-date", "2027-13-40", 20270101, ""):
            with self.subTest(maturity_date=bad), self.assertRaises(ValidationError):
                parse_trade(make_payload(maturity_date=bad), TODAY)

    def test_non_object_payload_is_rejected(self):
        for bad in (None, [], "text", 5):
            with self.subTest(payload=bad), self.assertRaises(ValidationError):
                parse_trade(bad, TODAY)


if __name__ == "__main__":
    unittest.main()
