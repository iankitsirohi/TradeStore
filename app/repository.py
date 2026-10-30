"""SQLite persistence. Uses one short-lived connection per operation so it is safe
with threads and multiple gunicorn workers; writes use BEGIN IMMEDIATE so the
check-then-write in the service is atomic."""
import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import List, Optional

from .models import Trade

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id         TEXT    NOT NULL,
    version          INTEGER NOT NULL,
    counter_party_id TEXT    NOT NULL,
    portfolio_id     TEXT    NOT NULL,
    maturity_date    TEXT    NOT NULL,
    created_date     TEXT    NOT NULL,
    expired          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (trade_id, version)
);
CREATE INDEX IF NOT EXISTS idx_trades_active_maturity
    ON trades (maturity_date) WHERE expired = 0;
"""


def _to_trade(row) -> Trade:
    return Trade(
        trade_id=row["trade_id"],
        version=row["version"],
        counter_party_id=row["counter_party_id"],
        portfolio_id=row["portfolio_id"],
        maturity_date=date.fromisoformat(row["maturity_date"]),
        created_date=date.fromisoformat(row["created_date"]),
        expired=bool(row["expired"]),
    )


class TradeRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")

    def init_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript(_SCHEMA)

    # --- writes (take part in a caller-managed transaction) -----------------
    def max_version(self, conn, trade_id: str) -> Optional[int]:
        row = conn.execute("SELECT MAX(version) AS v FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
        return row["v"]

    def upsert(self, conn, trade: Trade) -> bool:
        """Insert or replace. Returns True if an existing record was replaced."""
        existed = conn.execute(
            "SELECT 1 FROM trades WHERE trade_id = ? AND version = ?", (trade.trade_id, trade.version)
        ).fetchone() is not None
        conn.execute(
            "INSERT OR REPLACE INTO trades (trade_id, version, counter_party_id, portfolio_id,"
            " maturity_date, created_date, expired) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                trade.trade_id, trade.version, trade.counter_party_id, trade.portfolio_id,
                trade.maturity_date.isoformat(), trade.created_date.isoformat(), int(trade.expired),
            ),
        )
        return existed

    def expire_before(self, today: date) -> int:
        """Flag every live trade whose maturity date is earlier than ``today``."""
        with self._connection() as conn:
            cur = conn.execute(
                "UPDATE trades SET expired = 1 WHERE expired = 0 AND maturity_date < ?", (today.isoformat(),)
            )
            return cur.rowcount

    # --- reads ---------------------------------------------------------------
    def get(self, trade_id: str, version: Optional[int] = None) -> Optional[Trade]:
        with self._connection() as conn:
            if version is None:
                row = conn.execute(
                    "SELECT * FROM trades WHERE trade_id = ? ORDER BY version DESC LIMIT 1", (trade_id,)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM trades WHERE trade_id = ? AND version = ?", (trade_id, version)
                ).fetchone()
        return _to_trade(row) if row else None

    def list_all(self) -> List[Trade]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM trades ORDER BY trade_id, version").fetchall()
        return [_to_trade(r) for r in rows]

    def list_versions(self, trade_id: str) -> List[Trade]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE trade_id = ? ORDER BY version", (trade_id,)
            ).fetchall()
        return [_to_trade(r) for r in rows]
