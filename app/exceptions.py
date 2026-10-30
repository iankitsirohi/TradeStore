"""Domain exceptions. Each carries the HTTP status and machine-readable code used by the API."""


class TradeStoreError(Exception):
    status_code = 400
    code = "trade_store_error"


class ValidationError(TradeStoreError):
    status_code = 422
    code = "validation_error"


class LowerVersionError(TradeStoreError):
    """A trade with a lower version than the stored one was received."""

    status_code = 409
    code = "lower_version"


class PastMaturityDateError(TradeStoreError):
    """The trade's maturity date is earlier than today."""

    status_code = 422
    code = "past_maturity_date"


class TradeNotFoundError(TradeStoreError):
    status_code = 404
    code = "trade_not_found"
