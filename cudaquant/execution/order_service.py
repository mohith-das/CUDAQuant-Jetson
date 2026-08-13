"""Order execution service — the ONLY sanctioned entry point for order submission.

Every order, paper or live, must pass through this service's three gates
in order:
  1. Config gate: effective trading mode (TradingModeService or TRADING_MODE)
  2. RiskGovernor.pre_trade_check()
  3. KillSwitch.is_engaged()

No other code path may call AlpacaBroker.submit_order() directly.

The service also owns the runtime mode switch plumbing: ``set_mode()``
rebuilds the broker for the new mode's endpoint (paper/live) and flips the
governor's live flag, so switching from the UI is atomic w.r.t. order flow.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from cudaquant.config.settings import settings
from cudaquant.data.schemas import Order
from cudaquant.providers.alpaca_broker import AlpacaBroker
from cudaquant.risk.governor import RiskGovernor
from cudaquant.risk.kill_switch import KillSwitch

logger = logging.getLogger(__name__)


def _default_mode_provider() -> str:
    """Boot-time fallback: read TRADING_MODE from settings (env/.env only).

    The shared TradingModeService replaces this at runtime wiring
    (build_order_service) so the *effective* persisted mode is used.
    """
    return settings.TRADING_MODE


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
        mode_provider: Callable[[], str] | None = None,
        broker_factory: Callable[[bool], Any] | None = None,
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
        self._mode_provider = mode_provider
        self._broker_factory = broker_factory or (lambda paper: AlpacaBroker(paper=paper))
        self._runtime_mode: str | None = None

    # ── Runtime mode switch plumbing ─────────────────────────────────────────

    def set_mode(self, mode: str, paper: bool) -> None:
        """Apply a runtime mode switch: rebuild broker + flip governor flag.

        ``paper`` selects the broker endpoint for the new mode. The governor's
        live flag is set via ``set_live_mode``, which re-verifies the
        environment gates itself (never enabling live casually).
        """
        self._runtime_mode = mode
        self._governor.set_live_mode(mode == "live")
        self._broker = self._broker_factory(paper)
        logger.info("OrderService mode applied: mode=%s paper=%s", mode, paper)

    def verify_live_connection(self) -> tuple[bool, str]:
        """Probe the live broker endpoint without placing any order.

        Used by TradingModeService before a paper→live switch.
        """
        try:
            probe = self._broker_factory(False)
            if getattr(probe, "is_connected", False):
                return True, "live broker connected"
            return (
                False,
                "live broker not connected — check ALPACA_API_KEY/ALPACA_SECRET_KEY "
                "(paper-only keys cannot trade live)",
            )
        except Exception as e:
            logger.error("Live broker probe failed: %s", e)
            return False, f"live broker probe failed: {e}"

    def submit_order(self, order: Order) -> tuple[bool, str, str | None]:
        """Submit an order through all safety gates.

        Returns:
            (success, message, order_id_or_none)
        """
        # ── Gate 1: Config gate ──────────────────────────────────────────
        mode = self._mode_provider() if self._mode_provider else _default_mode_provider()

        if mode not in ("paper", "live"):
            return False, f"invalid TRADING_MODE: {mode}", None

        if mode == "live" and not KillSwitch.is_live_ack_enabled():
            return False, (
                "live trading not enabled "
                "(ENABLE_LIVE_TRADING ack missing in .env)"
            ), None

        # ── Gate 2: Risk Governor ────────────────────────────────────────
        # Fetch account state once — needed for both ref_price and risk check
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
            logger.info("Order submitted: id=%s symbol=%s side=%s qty=%s",
                         order_id, order.symbol, order.side.value, order.qty)

            # Record the fill for daily risk-limit tracking.
            # Uses ref_price for notional estimation; real P&L from broker fills
            # would replace this estimate in a live system.
            self._governor.record_fill({
                "symbol": order.symbol,
                "side": order.side.value,
                "qty": order.qty,
                "price": ref_price,
                "pnl": 0.0,  # Real P&L requires broker fill confirmation — placeholder
                "order_id": order_id,
            })

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


# ── Production wiring ────────────────────────────────────────────────────────

_shared_order_service: OrderService | None = None


def build_order_service(db_path: str | None = None) -> OrderService:
    """Build (once) the shared OrderService bound to the TradingModeService.

    The mode provider reads the *effective* runtime mode so gate 1 follows
    UI switches; the broker factory rebuilds the broker for the new mode's
    endpoint on switch. The TradingModeService gets a back-reference so
    ``switch()`` can drive this service and probe the live broker.
    """
    global _shared_order_service
    if _shared_order_service is not None:
        return _shared_order_service

    from cudaquant.execution.trading_mode import get_shared_trading_mode

    trading_mode = get_shared_trading_mode(db_path)
    _shared_order_service = OrderService(
        mode_provider=lambda: trading_mode.effective_mode,
        broker_factory=lambda paper: AlpacaBroker(paper=paper),
    )
    trading_mode.bind_order_service(_shared_order_service)
    return _shared_order_service
