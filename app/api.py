from flask import Blueprint, current_app, jsonify, request

from .exceptions import TradeStoreError, ValidationError

bp = Blueprint("trades", __name__)


def _service():
    return current_app.extensions["trade_service"]


@bp.get("/health")
def health():
    return jsonify(status="ok")


@bp.post("/trades")
def submit_trade():
    payload = request.get_json(silent=True)
    trade, created = _service().submit_trade(payload)
    return jsonify(trade.to_dict()), 201 if created else 200


@bp.get("/trades")
def list_trades():
    expired = None
    raw = request.args.get("expired")
    if raw is not None:
        if raw.lower() not in ("true", "false"):
            raise ValidationError("'expired' must be 'true' or 'false'")
        expired = raw.lower() == "true"
    return jsonify([t.to_dict() for t in _service().list_trades(expired)])


@bp.post("/trades/expire")
def expire_trades():
    return jsonify(expired_count=_service().expire_trades())


@bp.get("/trades/<trade_id>")
def get_trade(trade_id):
    return jsonify(_service().get_trade(trade_id).to_dict())


@bp.get("/trades/<trade_id>/versions")
def list_versions(trade_id):
    return jsonify([t.to_dict() for t in _service().list_versions(trade_id)])


@bp.get("/trades/<trade_id>/versions/<int:version>")
def get_version(trade_id, version):
    return jsonify(_service().get_trade(trade_id, version).to_dict())


def register_error_handlers(app):
    @app.errorhandler(TradeStoreError)
    def handle_domain_error(err):
        return jsonify(error=err.code, message=str(err)), err.status_code

    @app.errorhandler(404)
    def handle_not_found(_err):
        return jsonify(error="not_found", message="resource not found"), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(_err):
        return jsonify(error="method_not_allowed", message="method not allowed"), 405
