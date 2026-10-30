import os
from datetime import date

from flask import Flask

from .api import bp, register_error_handlers
from .repository import TradeRepository
from .scheduler import ExpiryScheduler
from .service import TradeService


def create_app(config=None, today_provider=date.today, start_scheduler=False):
    app = Flask(__name__)
    app.config.update(
        DATABASE_PATH=os.environ.get("TRADE_DB_PATH", "trades.db"),
        EXPIRY_INTERVAL_SECONDS=float(os.environ.get("EXPIRY_INTERVAL_SECONDS", "60")),
    )
    if config:
        app.config.update(config)

    repository = TradeRepository(app.config["DATABASE_PATH"])
    repository.init_schema()
    service = TradeService(repository, today=today_provider)

    scheduler = None
    if start_scheduler:
        scheduler = ExpiryScheduler(service.expire_trades, app.config["EXPIRY_INTERVAL_SECONDS"])
        scheduler.start()

    app.extensions["trade_service"] = service
    app.extensions["expiry_scheduler"] = scheduler
    app.register_blueprint(bp)
    register_error_handlers(app)
    return app
