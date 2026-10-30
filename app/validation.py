"""Turns an untrusted JSON payload into a :class:`Trade`."""
from datetime import date, datetime

from .exceptions import ValidationError
from .models import Trade

MAX_ID_LENGTH = 64
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")


def _required(payload, field):
    if field not in payload or payload[field] is None:
        raise ValidationError(f"'{field}' is required")
    return payload[field]


def _identifier(payload, field):
    value = _required(payload, field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"'{field}' must be a non-empty string")
    value = value.strip()
    if len(value) > MAX_ID_LENGTH:
        raise ValidationError(f"'{field}' must be at most {MAX_ID_LENGTH} characters")
    return value


def _version(payload):
    value = _required(payload, "version")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError("'version' must be an integer >= 1")
    return value


def _date(value, field):
    if isinstance(value, str):
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    raise ValidationError(f"'{field}' must be a date formatted YYYY-MM-DD or DD/MM/YYYY")


def parse_trade(payload, today: date) -> Trade:
    if not isinstance(payload, dict):
        raise ValidationError("request body must be a JSON object")

    maturity = _date(_required(payload, "maturity_date"), "maturity_date")
    created = today
    if payload.get("created_date") is not None:
        created = _date(payload["created_date"], "created_date")
        if created > today:
            raise ValidationError("'created_date' must not be in the future")

    return Trade(
        trade_id=_identifier(payload, "trade_id"),
        version=_version(payload),
        counter_party_id=_identifier(payload, "counter_party_id"),
        portfolio_id=_identifier(payload, "portfolio_id"),
        maturity_date=maturity,
        created_date=created,
        expired=False,  # always derived by the store, never client supplied
    )
