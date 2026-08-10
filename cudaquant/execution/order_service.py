"""Order execution service — the ONLY sanctioned entry point for order submission.

Every order, paper or live, must pass through this service's three gates
in order:
  1. Config gate: TRADING_MODE + ENABLE_LIVE_TRADING
  2. RiskGovernor.pre_trade_check()
  3. KillSwitch.is_engaged()

No other code path may call AlpacaBroker.submit_order() directly.
"""

from __future__ import annotations

import logging
from typing import Any

from cudaquant.config.settings import settings
from cudaquant.data.schemas import Order
from cudaquant.providers.alpaca_broker import AlpacaBroker
from cudaquant.risk.governor import RiskGovernor
from cudaquant.risk.kill_switch import KillSwitch

logger = logging.getLogger(__name__)


class OrderService:
    """Centralized order submission with mandatory safety gates.

    All three gates run in order. If any gate fails, the order is rejected
    with a specific reason — it is never silently swallowed.
    """

    def __init__(
        self,
        broker: AlpacaBroker | None = None,
        governor: RiskGovernor | None = None,
        kill_switch: KillSwitch | None = None,
    ):
        self._broker = broker or AlpacaBroker()
        self._governor = governor or RiskGovernor({
            "max_position_notional": settings.MAX_POSITION_NOTIONAL,
            "max_total_exposure": settings.MAX_TOTAL_EXPOSURE,
            "max_daily_trades": settings.MAX_DAILY_TRADES,
            "max_daily_loss": settings.MAX_DAILY_LOSS,
            "max_drawdown_pct": settings.MAX_DRAWDOWN_PCT,
            "symbol_allowlist": None,
        })
        self._kill_switch = kill_switch or KillSwitch(settings.KILL_SWITCH_FILE)

    def submit_order(self, order: Order) -> tuple[bool, str, str | None]:
        """Submit an order through all safety gates.

        Returns:
            (success, message, order_id_or_none)
        """
        # ── Gate 1: Config gate ──────────────────────────────────────────
        mode = settings.TRADING_MODE
        live_enabled = settings.live_trading_enabled

        if mode not in ("paper", "live"):
            return False, f"invalid TRADING_MODE: {mode}", None

        if mode == "live" and not live_enabled:
            return False, "live trading not enabled (ENABLE_LIVE_TRADING=False)", None

        if mode == "paper" and settings.ENABLE_LIVE_TRADING:
            return False, "paper mode but ENABLE_LIVE_TRADING=True — inconsistent config", None

        # ── Gate 2: Risk Governor ────────────────────────────────────────
        # Fetch account state first — needed for both ref_price and risk check
        try:
            account = self._broker.get_account()
            positions = self._broker.get_positions()
        except Exception as e:
            logger.error("Failed to get account state for risk check: %s", e)
            return False, f"risk check failed: cannot get account state ({e})", None

        # Build reference price for notional calculation.
        # For market orders (no limit_price), estimate from account state.
        if order.limit_price:
            ref_price = order.limit_price
        else:
            total_pos = sum(abs(p.qty) for p in positions)
            ref_price = max(
                account.portfolio_value / max(total_pos, 1) if total_pos > 0 else 100.0,
                10.0,  # floor: assume at least $10/share
            )
        order_payload = {
            "symbol": order.symbol,
            "side": order.side.value,
            "qty": order.qty,
            "price": ref_price,
        }

        # Get current account state for exposure checks
        try:
            account = self._broker.get_account()
            positions = self._broker.get_positions()
        except Exception as e:
            logger.error("Failed to get account state for risk check: %s", e)
            return False, f"risk check failed: cannot get account state ({e})", None

        # Build position dict for governor
        pos_dict = {p.symbol: p.qty for p in positions}
        prices = {order.symbol: order.limit_price or 0.0}
        account_dict = {"cash": account.cash, "equity": account.portfolio_value}

        approved, reason = self._governor.pre_trade_check(
            order_payload, account_dict, pos_dict, prices,
        )
        if not approved:
            logger.warning("RiskGovernor rejected order: %s", reason)
            return False, f"risk governor rejected: {reason}", None

        # ── Gate 3: Kill Switch ──────────────────────────────────────────
        if self._kill_switch.is_engaged():
            logger.warning("Kill switch engaged — rejecting order")
            return False, "kill switch is engaged", None

        # ── Submit ───────────────────────────────────────────────────────
        try:
            if not self._broker.is_connected:
                return False, "broker not connected", None

            order_id = self._broker.submit_order(order)
            logger.info("Order submitted: id=%s symbol=%s side=%s qty=%d",
                         order_id, order.symbol, order.side.value, order.qty)
            return True, "order submitted", order_id

        except Exception as e:
            logger.error("Order submission failed: %s", e)
            return False, f"broker error: {e}", None

    def get_account(self) -> Any:
        return self._broker.get_account()

    def get_positions(self) -> list:
        return self._broker.get_positions()

    def list_orders(self, status: str = "all", limit: int = 50) -> list[dict]:
        return self._broker.list_orders(status=status, limit=limit)

    def cancel_order(self, order_id: str) -> bool:
        return self._broker.cancel_order(order_id)

    def get_kill_switch_state(self) -> dict:
        return self._kill_switch.status()

    def engage_kill_switch(self, reason: str = "manual") -> None:
        self._kill_switch.engage(reason)

    def disengage_kill_switch(self) -> None:
        self._kill_switch.disengage()

    @property
    def is_broker_connected(self) -> bool:
        return self._broker.is_connected
