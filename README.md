# Trade Store

REST API (Python / Flask / SQLite) that receives trades and stores them under these rules:

1. A trade with a **lower version** than the stored one is **rejected** (`409 lower_version`).
   The **same version replaces** the current record (`200`); a higher version is stored as a new version (`201`).
2. A trade whose **maturity date is earlier than today** is **rejected** (`422 past_maturity_date`).
3. When a trade's maturity date has passed it is **automatically marked `expired`** - by a background
   scheduler and also on every read, so results are correct between scheduler runs.

Trades are keyed by `(trade_id, version)`, so the problem-statement table (T2 v1 and T2 v2) is representable.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python wsgi.py                              # dev, http://localhost:8000
# or: docker build -t trade-store . && docker run -p 8000:8000 -v trades:/data trade-store
```

Env vars: `TRADE_DB_PATH` (default `trades.db`), `EXPIRY_INTERVAL_SECONDS` (default `60`).

## API

| Method | Path | Description |
|---|---|---|
| POST | `/trades` | Submit a trade (201 new, 200 replaced) |
| GET | `/trades[?expired=true\|false]` | All stored trade versions |
| GET | `/trades/{id}` | Latest version |
| GET | `/trades/{id}/versions` | All versions |
| GET | `/trades/{id}/versions/{n}` | One version |
| POST | `/trades/expire` | Run the expiry sweep now |
| GET | `/health` | Liveness |

```bash
curl -X POST localhost:8000/trades -H 'Content-Type: application/json' -d '{
  "trade_id":"T1","version":1,"counter_party_id":"CP-1","portfolio_id":"B1","maturity_date":"2030-05-20"}'
```

Dates are `YYYY-MM-DD` or `DD/MM/YYYY`. `created_date` is optional (defaults to today); `expired` is always
computed by the store. Errors are JSON: `{"error": "<code>", "message": "..."}`
(`validation_error` 422, `past_maturity_date` 422, `lower_version` 409, `trade_not_found` 404).

## Tests / TDD

```bash
pytest tests/unit --cov=app      # unit tests (service, repository, validation, scheduler, API)
pytest tests/regression          # end-to-end scenarios from the problem statement
```

The git history follows red -> green: the failing tests were committed first, then the implementation.
Time is injected (`today_provider`), so expiry is tested deterministically.

## CI/CD (`.github/workflows/ci.yml`)

1. **unit-tests** - Python 3.11 and 3.12, coverage gate >= 90%.
2. **regression-tests** - end-to-end HTTP scenarios.
3. **dependency-vulnerability-scan** - Trivy scans `requirements*.txt`; **the build fails on any CRITICAL finding**
   (Trivy's highest severity; there is no separate "blocker" level). Lower severities are reported only.
4. **build-and-deploy** (main only) - builds the Docker image, scans it (fails on CRITICAL), pushes to GHCR.

## Design diagrams (PlantUML, `docs/`)

`class-diagram.puml`, `sequence-submit-trade.puml`, `sequence-expiry.puml`

## Design notes

- Check-then-write uses `BEGIN IMMEDIATE`, so concurrent submissions cannot slip a lower version past the check,
  also across multiple gunicorn workers. For multi-host deployments swap SQLite for PostgreSQL behind `TradeRepository`.
- A trade expires the day *after* its maturity date (maturity day itself is still live).
