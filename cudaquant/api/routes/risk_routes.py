"""Risk & Execution API routes."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from cudaquant.alerts.telegram import TelegramAlerter
from cudaquant.api.auth import require_auth
from cudaquant.config.settings import settings
from cudaquant.data.schemas import Order, OrderSide, OrderType
from cudaquant.execution.order_service import build_order_service
from cudaquant.execution.trading_mode import get_shared_trading_mode

risk_router = APIRouter(prefix="/api/risk", tags=["risk"], dependencies=[Depends(require_auth)])
exec_router = APIRouter(prefix="/api/execution", tags=["execution"], dependencies=[Depends(require_auth)])

# Shared OrderService — bound to the shared TradingModeService (see
# build_order_service) so mode switches rebuild the broker and gate 1 follows
# the effective mode.
_order_service = build_order_service(settings.DUCKDB_PATH)


# ── Risk routes ──────────────────────────────────────────────────────────────

@risk_router.get("/")
def risk_status():
    """Get current risk + trading-mode state."""
    ks = _order_service.get_kill_switch_state()
    tm = get_shared_trading_mode(settings.DUCKDB_PATH).get_state()
    return {
        "trading_mode": tm["effective_mode"],
        "desired_mode": tm["desired_mode"],
        "mode_reason": tm["mode_reason"],
        "env_live_eligible": tm["env_live_eligible"],
        "live_trading_enabled": tm["effective_mode"] == "live",
        "kill_switch_engaged": ks["engaged"],
        "kill_switch_reason": ks.get("reason"),
        "broker_connected": _order_service.is_broker_connected,
    }


@risk_router.put("/trading-mode")
def set_trading_mode(payload: dict):
    """Switch trading mode: paper or live.

    live→paper: always allowed.
    paper→live: requires the .env acknowledgement gates, ``confirm="LIVE"``,
    a disarmed kill switch, and a verified live broker connection.
    """
    mode = payload.get("mode", "")
    confirm = payload.get("confirm", "")
    tm = get_shared_trading_mode(settings.DUCKDB_PATH)
    ok, message = tm.switch(mode, confirm=confirm)
    if not ok:
        raise HTTPException(403, message)
    return {
        "success": True,
        "effective_mode": tm.effective_mode,
        "desired_mode": tm.state.desired,
        "message": message,
    }


@risk_router.post("/kill-switch")
def engage_kill_switch(payload: dict):
    """Engage the kill switch. Requires explicit confirmation."""
    confirm = payload.get("confirm", "")
    if confirm != "STOP":
        raise HTTPException(400, "Must include {'confirm': 'STOP'} to engage kill switch")
    reason = payload.get("reason", "manual")
    _order_service.engage_kill_switch(reason=reason)
    TelegramAlerter().send(
        f"[CUDAQuant] Kill switch engaged — reason: {reason} — "
        f"{datetime.now(timezone.utc).isoformat()}"
    )
    return {"kill_switch_engaged": True}


@risk_router.delete("/kill-switch")
def disengage_kill_switch():
    _order_service.disengage_kill_switch()
    return {"kill_switch_engaged": False}


# ── Execution routes ─────────────────────────────────────────────────────────

@exec_router.get("/account")
def get_account():
    try:
        acct = _order_service.get_account()
        return {"cash": acct.cash, "portfolio_value": acct.portfolio_value,
                "buying_power": acct.buying_power}
    except Exception as e:
        raise HTTPException(503, f"Broker unavailable: {e}") from e


@exec_router.get("/positions")
def get_positions():
    positions = _order_service.get_positions()
    return [{"symbol": p.symbol, "qty": p.qty, "market_value": p.market_value,
             "unrealized_pnl": p.unrealized_pnl} for p in positions]


@exec_router.get("/orders")
def list_orders(status: str = "all", limit: int = 50):
    return _order_service.list_orders(status=status, limit=limit)


@exec_router.post("/orders")
def submit_order(payload: dict):
    """Submit an order through OrderService (all three gates enforced)."""
    try:
        order = Order(
            symbol=payload["symbol"],
            side=OrderSide(payload["side"]),
            order_type=OrderType(payload.get("order_type", "market")),
            qty=payload["qty"],
            limit_price=payload.get("limit_price"),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(400, f"Invalid order: {e}") from e

    ok, msg, order_id = _order_service.submit_order(order)
    if not ok:
        raise HTTPException(403, msg) if "kill" in msg.lower() or "governor" in msg.lower() else HTTPException(400, msg)

    return {"success": True, "order_id": order_id, "message": msg}
