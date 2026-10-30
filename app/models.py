from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Trade:
    trade_id: str
    version: int
    counter_party_id: str
    portfolio_id: str
    maturity_date: date
    created_date: date
    expired: bool = False

    def to_dict(self):
        return {
            "trade_id": self.trade_id,
            "version": self.version,
            "counter_party_id": self.counter_party_id,
            "portfolio_id": self.portfolio_id,
            "maturity_date": self.maturity_date.isoformat(),
            "created_date": self.created_date.isoformat(),
            "expired": self.expired,
        }
