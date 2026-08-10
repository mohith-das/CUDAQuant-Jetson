"""Risk governor — the single gate every order must pass.

All execution (paper or live) flows through ``pre_trade_check``. The governor
FAILS CLOSED: any unknown, unreadable, or exceptional state rejects the order
with a reason string. There is no code path that bypasses the governor.

Order/account/positions/price shapes are plain dicts so any execution layer
(backtest, paper, or live) can integrate without a shared ORM:

- ``order``: ``{"symbol": str, "side": "buy"|"sell", "qty": positive,
  "price": optional limit price}``
- ``account``: ``{"cash": float, "equity": optional, "last_updated": optional}``
- ``positions``: ``{symbol: qty}`` or ``{symbol: {"qty": qty}}``
- ``current_prices``: ``{symbol: price}`` or ``{symbol: {"price": price,
  "timestamp": optional ISO timestamp}}``
"""

from __future__ import annotations

from datetime import datetime, timezone

from cudaquant.risk.kill_switch import KillSwitch

VALID_SIDES = frozenset({"buy", "sell"})


class RiskGovernor:
    """Centralized risk checks. Unknown safety state → FAIL CLOSED."""

    def __init__(self, config: dict):
        self.max_position_notional = float(config.get("max_position_notional", 100_000))
        self.max_total_exposure = float(config.get("max_total_exposure", 500_000))
        self.max_daily_trades = int(config.get("max_daily_trades", 50))
        self.max_daily_loss = float(config.get("max_daily_loss", 5_000))
        self.max_drawdown_pct = float(config.get("max_drawdown_pct", 20))
        self.max_data_age_seconds = float(config.get("max_data_age_seconds", 60.0))
        self.symbol_allowlist: list[str] | None = config.get("symbol_allowlist")
        self._kill_switch = KillSwitch(config.get("kill_switch_file", "./.kill_switch"))
        self._daily_trades = 0
        self._daily_pnl = 0.0
        self._kill_switched = False
        self._live_mode = False
        self._peak_equity = 0.0

    # ------------------------------------------------------------------ #
    # Mode / lifecycle
    # ------------------------------------------------------------------ #
    def set_live_mode(self, enabled: bool) -> bool:
        """Live mode requires multiple explicit gates — never enable casually.

        Refuses to enable unless the environment gates
        (``TRADING_MODE=live`` AND
        ``ENABLE_LIVE_TRADING=I_UNDERSTAND_LIVE_TRADING_RISK``) are satisfied.
        Returns whether the requested mode took effect.
        """
        if enabled and not KillSwitch.is_live_mode_enabled():
            return False
        self._live_mode = bool(enabled)
        return True

    def kill(self, reason: str = "manual") -> None:
        """Activate kill switch. Persists to file for cross-process safety."""
        self._kill_switched = True
        self._kill_switch.engage(reason=reason)

    def is_alive(self) -> bool:
        """Check kill switch. Read from file for cross-process safety."""
        return not self._kill_switched and not self._kill_switch.is_engaged()

    def reset_daily(self) -> None:
        """Reset daily counters."""
        self._daily_trades = 0
        self._daily_pnl = 0.0

    def get_state(self) -> dict:
        """Current risk state for UI."""
        return {
            "live_mode": self._live_mode,
            "kill_switched": self._kill_switched,
            "alive": self.is_alive(),
            "daily_trades": self._daily_trades,
            "daily_trades_limit": self.max_daily_trades,
            "daily_pnl": self._daily_pnl,
            "daily_loss_limit": self.max_daily_loss,
            "peak_equity": self._peak_equity,
            "max_position_notional": self.max_position_notional,
            "max_total_exposure": self.max_total_exposure,
            "max_drawdown_pct": self.max_drawdown_pct,
        }

    # ------------------------------------------------------------------ #
    # Pre-trade gate
    # ------------------------------------------------------------------ #
    def pre_trade_check(self, order, account, positions, current_prices) -> tuple[bool, str]:
        """Returns ``(approved, reason)``. Checks all limits, fail closed."""
        if not self.is_alive():
            return (False, "kill_switch_engaged")

        try:
            symbol = str(order.get("symbol", ""))
            if not symbol:
                return (False, "missing_symbol")
            side = str(order.get("side", "")).lower()
            if side not in VALID_SIDES:
                return (False, "invalid_side")
            qty = float(order.get("qty", 0.0))
            if qty <= 0:
                return (False, "invalid_qty")

            if self.symbol_allowlist is not None and symbol not in self.symbol_allowlist:
                return (False, "symbol_not_allowed")

            price = self._reference_price(order, current_prices)
            if price is None:
                return (False, "no_price_data")
            if price <= 0:
                return (False, "invalid_price")
            if not self._data_is_fresh(order, account, current_prices):
                return (False, "stale_data")

            notional = qty * price
            if notional > self.max_position_notional:
                return (False, "position_notional_exceeded")

            exposure = self._current_exposure(positions, current_prices)
            if exposure is None:
                return (False, "exposure_unknown")
            if exposure + notional > self.max_total_exposure:
                return (False, "total_exposure_exceeded")

            if self._daily_trades >= self.max_daily_trades:
                return (False, "daily_trade_limit_reached")
            if self._daily_pnl <= -self.max_daily_loss:
                return (False, "daily_loss_limit_reached")

            equity = self._current_equity(account, positions, current_prices)
            if equity is None:
                return (False, "equity_unknown")
            if equity <= 0:
                return (False, "non_positive_equity")
            self._peak_equity = max(self._peak_equity, equity)
            if self._peak_equity > 0:
                drawdown = (self._peak_equity - equity) / self._peak_equity
                if drawdown >= self.max_drawdown_pct / 100.0:
                    return (False, "max_drawdown_exceeded")

            return (True, "approved")
        except Exception as exc:  # noqa: BLE001 — fail closed on any error
            return (False, f"fail_closed: {type(exc).__name__}: {exc}")

    def record_fill(self, fill: dict) -> None:
        """Update daily trade count and PnL tracking after an execution."""
        self._daily_trades += 1
        self._daily_pnl += float(fill.get("pnl", 0.0))
        equity = fill.get("equity")
        if equity is not None:
            self._peak_equity = max(self._peak_equity, float(equity))

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _reference_price(order: dict, current_prices: dict) -> float | None:
        """Order limit price if given, else the symbol's current price."""
        limit = order.get("price")
        if limit is not None:
            return float(limit)
        raw = current_prices.get(order.get("symbol", ""))
        if isinstance(raw, dict):
            raw = raw.get("price")
        if raw is None:
            return None
        return float(raw)

    def _data_is_fresh(self, order: dict, account: dict, current_prices: dict) -> bool:
        """Reject orders whose price data is older than the staleness limit.

        Staleness is only judged when timestamp information is present; plain
        floats carry no timestamp and cannot be judged stale.
        """
        now = datetime.now(timezone.utc)
        raw = current_prices.get(order.get("symbol", ""))
        if isinstance(raw, dict) and raw.get("timestamp") is not None:
            ts = _parse_timestamp(raw["timestamp"])
            if ts is None or (now - ts).total_seconds() > self.max_data_age_seconds:
                return False
        account_ts = account.get("last_updated") if isinstance(account, dict) else None
        if account_ts is not None:
            ts = _parse_timestamp(account_ts)
            if ts is None or (now - ts).total_seconds() > self.max_data_age_seconds:
                return False
        return True

    def _current_exposure(self, positions: dict, current_prices: dict) -> float | None:
        """Marked-to-market exposure of all positions, or None if unpriced."""
        if not positions:
            return 0.0
        total = 0.0
        for symbol, value in positions.items():
            qty = _position_qty(value)
            price = _price(current_prices.get(symbol))
            if qty is None or price is None:
                return None
            total += qty * price
        return total

    def _current_equity(self, account: dict, positions: dict, current_prices: dict) -> float | None:
        """Equity = cash + marked-to-market positions (or account-provided)."""
        if not isinstance(account, dict):
            return None
        if account.get("equity") is not None:
            return float(account["equity"])
        if account.get("cash") is None:
            return None
        exposure = self._current_exposure(positions, current_prices)
        if exposure is None:
            return None
        return float(account["cash"]) + exposure


def _position_qty(value) -> float | None:
    if isinstance(value, dict):
        value = value.get("qty")
    if value is None:
        return None
    return float(value)


def _price(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("price")
    if value is None:
        return None
    return float(value)


def _parse_timestamp(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        # Unparseable timestamps are not "fresh" evidence; skip the check
        # rather than mis-failing, the order itself is judged by other checks.
        return None
