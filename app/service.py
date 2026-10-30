"""Business rules of the trade store."""
from datetime import date
from typing import Callable, List, Optional, Tuple

from .exceptions import LowerVersionError, PastMaturityDateError, TradeNotFoundError
from .models import Trade
from .repository import TradeRepository
from .validation import parse_trade


class TradeService:
    def __init__(self, repository: TradeRepository, today: Callable[[], date] = date.today):
        self._repo = repository
        self._today = today

    def submit_trade(self, payload) -> Tuple[Trade, bool]:
        """Validate and store a trade. Returns ``(trade, created)``; ``created`` is
        False when an existing record with the same version was replaced."""
        today = self._today()
        trade = parse_trade(payload, today)

        if trade.maturity_date < today:
            raise PastMaturityDateError(
                f"maturity date {trade.maturity_date.isoformat()} is earlier than today ({today.isoformat()})"
            )

        with self._repo.transaction() as conn:
            latest = self._repo.max_version(conn, trade.trade_id)
            if latest is not None and trade.version < latest:
                raise LowerVersionError(
                    f"trade {trade.trade_id} version {trade.version} is lower than stored version {latest}"
                )
            replaced = self._repo.upsert(conn, trade)
        return trade, not replaced

    def expire_trades(self) -> int:
        return self._repo.expire_before(self._today())

    # Reads sweep first so results are correct even if the scheduler has not run yet.
    def get_trade(self, trade_id: str, version: Optional[int] = None) -> Trade:
        self.expire_trades()
        trade = self._repo.get(trade_id, version)
        if trade is None:
            suffix = f" version {version}" if version is not None else ""
            raise TradeNotFoundError(f"trade {trade_id}{suffix} not found")
        return trade

    def list_versions(self, trade_id: str) -> List[Trade]:
        self.expire_trades()
        versions = self._repo.list_versions(trade_id)
        if not versions:
            raise TradeNotFoundError(f"trade {trade_id} not found")
        return versions

    def list_trades(self, expired: Optional[bool] = None) -> List[Trade]:
        self.expire_trades()
        trades = self._repo.list_all()
        if expired is not None:
            trades = [t for t in trades if t.expired is expired]
        return trades
