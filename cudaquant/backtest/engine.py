"""Deterministic, reproducible backtesting engine.

Walk-forward, bar-by-bar simulation with these guarantees:

- No look-ahead: the signal function only ever receives rows up to and
  including the current bar.
- Execution delay: a signal computed on bar ``t`` fills at bar ``t+1``'s open.
- Every fill goes through ``apply_costs`` (commission + spread + slippage),
  so cost accounting is identical to the standalone cost model.
- Determinism: the engine has no wall-clock or environment dependence; the
  internal RNG is seeded and any user ``signal_fn`` that is itself
  deterministic yields identical runs.

Data layout: one row per (symbol, timestamp) bar with columns
``symbol, timestamp, open, high, low, close, volume``. The engine sorts by
``(timestamp, symbol, row_order)`` so ties are broken deterministically. For
symbol-specific backtests pass single-symbol data; multi-symbol frames are
treated as one interleaved timeline (each bar's signal trades the symbol of
the next bar's row).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable

import pandas as pd

from cudaquant.backtest.costs import CostModel, apply_costs
from cudaquant.backtest.metrics import compute_metrics

REQUIRED_COLUMNS = ("symbol", "timestamp", "open", "high", "low", "close", "volume")

SignalFn = Callable[[pd.DataFrame], "pd.Series | float"]


class DeterministicBacktester:
    """Deterministic, reproducible backtesting engine."""

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission_per_share: float = 0.005,
        slippage_bps: float = 1.0,  # basis points
        spread_bps: float = 1.0,
        seed: int = 42,
    ):
        self.initial_capital = float(initial_capital)
        self.commission_per_share = float(commission_per_share)
        self.slippage_bps = float(slippage_bps)
        self.spread_bps = float(spread_bps)
        self.seed = int(seed)
        self._cost_model = CostModel(
            commission_per_share=self.commission_per_share,
            slippage_bps=self.slippage_bps,
            spread_bps=self.spread_bps,
        )
        self._rng = random.Random(self.seed)

    def run(
        self,
        data: pd.DataFrame,
        signal_fn: SignalFn,
        max_position_pct: float = 0.10,
        long_only: bool = True,
    ) -> dict:
        """Run a backtest on OHLCV data with a signal function.

        Args:
            data: DataFrame with columns ``symbol, timestamp, open, high,
                low, close, volume``.
            signal_fn: receives the data available up to the current bar
                (inclusive) and returns a position signal in ``(-1, 0, 1)`` —
                a scalar or a Series whose last value is the signal.
            max_position_pct: cap on position notional as a fraction of
                current equity; the engine truncates share counts so the cap
                is never exceeded.
            long_only: when True, negative signals are treated as flat
                (no shorting).

        Returns:
            Dict with keys ``equity_curve`` (per-bar close equity),
            ``trades`` (closed round trips), and ``metrics`` (see
            ``compute_metrics``).
        """
        df = self._validate(data)
        n = len(df)
        if not callable(signal_fn):
            raise TypeError("signal_fn must be callable")
        if max_position_pct < 0:
            raise ValueError("max_position_pct must be non-negative")

        opens = df["open"].astype(float).to_numpy()
        closes = df["close"].astype(float).to_numpy()
        symbols = df["symbol"].tolist()
        timestamps = df["timestamp"].tolist()

        cash = self.initial_capital
        positions: dict[str, dict] = {}
        trades: list[dict] = []
        equity_curve: list[float] = []
        volume_traded = 0.0
        bars_in_market = 0
        target_signal = 0.0

        for i in range(n):
            # Fill the signal computed from the previous bar at this bar's open.
            if i > 0:
                cash, volume_traded = self._adjust_position(
                    symbol=symbols[i],
                    target_signal=target_signal,
                    price=float(opens[i]),
                    bar_time=timestamps[i],
                    bar_idx=i,
                    max_position_pct=max_position_pct,
                    cash=cash,
                    positions=positions,
                    trades=trades,
                    volume_traded=volume_traded,
                )

            # Compute the next target from data available through this bar.
            target_signal = self._coerce_signal(signal_fn(df.iloc[: i + 1]), long_only)

            # Mark equity at this bar's close.
            equity = cash
            if positions:
                bars_in_market += 1
                for pos in positions.values():
                    equity += pos["qty"] * closes[i]
            equity_curve.append(float(equity))

        metrics = compute_metrics(
            equity_curve,
            trades,
            self.initial_capital,
            n,
            volume_traded=volume_traded,
            bars_in_market=bars_in_market,
        )
        return {"equity_curve": equity_curve, "trades": trades, "metrics": metrics}

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _validate(self, data: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(data, pd.DataFrame) or data.empty:
            raise ValueError("data must be a non-empty DataFrame")
        missing = [c for c in REQUIRED_COLUMNS if c not in data.columns]
        if missing:
            raise ValueError(f"data missing required columns: {missing}")
        ohlc = data[["open", "high", "low", "close"]]
        if ohlc.isna().any().any():
            raise ValueError("data contains NaN in OHLC columns")
        if (data["open"] <= 0).any() or (data["close"] <= 0).any():
            raise ValueError("data contains non-positive open/close prices")

        # Deterministic ordering: timestamp, then symbol, then original row.
        df = data.copy()
        df["_row"] = range(len(df))
        df = (
            df.sort_values(["timestamp", "symbol", "_row"])
            .drop(columns="_row")
            .reset_index(drop=True)
        )
        return df

    @staticmethod
    def _coerce_signal(raw, long_only: bool) -> float:
        """Normalize a signal_fn result to a float in the supported range."""
        if isinstance(raw, pd.Series):
            sig = float(raw.iloc[-1]) if not raw.empty else 0.0
        else:
            sig = float(raw)
        if not math.isfinite(sig):
            sig = 0.0
        sig = max(-1.0, min(1.0, sig))
        if long_only:
            sig = max(0.0, sig)
        return sig

    def _adjust_position(
        self,
        symbol: str,
        target_signal: float,
        price: float,
        bar_time,
        bar_idx: int,
        max_position_pct: float,
        cash: float,
        positions: dict[str, dict],
        trades: list[dict],
        volume_traded: float,
    ) -> tuple[float, float]:
        """Rebalance ``symbol`` toward the target signal at ``price``.

        Position notional is capped at ``max_position_pct * current equity``.
        Positions are signed: positive is long, negative is short. A flip
        through zero is accounted as a close followed by an open. Returns the
        updated ``(cash, volume_traded)``.
        """
        pos = positions.get(symbol)
        held = pos["qty"] if pos else 0

        equity = cash
        for other in positions.values():
            equity += other["qty"] * price
        target_qty = int(target_signal * max_position_pct * equity / price)
        delta = target_qty - held
        if delta == 0:
            return cash, volume_traded

        side = "buy" if delta > 0 else "sell"
        qty = abs(delta)
        adj_price, _ = apply_costs(price, side, qty, self._cost_model)
        commission = self._cost_model.commission_per_share * qty
        volume_traded += qty * adj_price

        if side == "buy":
            cash -= qty * adj_price + commission
        else:
            cash += qty * adj_price - commission

        # Split flips through zero into a close and an (opposite) open.
        close_qty = 0
        open_qty = delta
        if pos and held != 0 and (delta > 0) != (held > 0):
            close_qty = min(qty, abs(held))
            open_qty = delta - (close_qty if delta > 0 else -close_qty)

        if close_qty:
            cash, positions = self._close_position(
                symbol=symbol,
                pos=pos,
                close_qty=close_qty,
                adj_price=adj_price,
                bar_time=bar_time,
                bar_idx=bar_idx,
                cash=cash,
                positions=positions,
                trades=trades,
            )
            pos = positions.get(symbol)

        if open_qty:
            self._open_or_add(
                symbol=symbol,
                pos=pos,
                open_qty=open_qty,
                adj_price=adj_price,
                bar_time=bar_time,
                bar_idx=bar_idx,
                positions=positions,
            )

        return cash, volume_traded

    def _close_position(
        self,
        symbol: str,
        pos: dict,
        close_qty: int,
        adj_price: float,
        bar_time,
        bar_idx: int,
        cash: float,
        positions: dict[str, dict],
        trades: list[dict],
    ) -> tuple[float, dict[str, dict]]:
        """Realize pnl for ``close_qty`` shares of an open position."""
        held = pos["qty"]
        is_long = held > 0
        if is_long:
            pnl = (adj_price - pos["entry_price"]) * close_qty
        else:
            pnl = (pos["entry_price"] - adj_price) * close_qty
        entry_comm_share = pos["entry_commission"] * (close_qty / abs(held))
        close_commission = self._cost_model.commission_per_share * close_qty
        pnl -= entry_comm_share + close_commission

        entry_notional = close_qty * pos["entry_price"]
        return_pct = pnl / entry_notional if entry_notional else 0.0

        trades.append(
            {
                "entry_time": pos["entry_time"],
                "exit_time": bar_time,
                "symbol": symbol,
                "side": "long" if is_long else "short",
                "entry_price": pos["entry_price"],
                "exit_price": adj_price,
                "qty": close_qty,
                "pnl": round(pnl, 10),
                "return_pct": round(return_pct, 10),
                "exit_reason": "signal",
                "entry_idx": pos["entry_idx"],
                "exit_idx": bar_idx,
            }
        )

        remaining = held - close_qty if is_long else held + close_qty
        if remaining == 0:
            del positions[symbol]
        else:
            pos["qty"] = remaining
            pos["entry_commission"] *= abs(remaining) / abs(held)
        return cash, positions

    def _open_or_add(
        self,
        symbol: str,
        pos: dict | None,
        open_qty: int,
        adj_price: float,
        bar_time,
        bar_idx: int,
        positions: dict[str, dict],
    ) -> None:
        """Open a new position or add to an existing one (same direction)."""
        commission = self._cost_model.commission_per_share * abs(open_qty)
        if pos is None:
            positions[symbol] = {
                "qty": open_qty,
                "entry_price": adj_price,
                "entry_time": bar_time,
                "entry_idx": bar_idx,
                "entry_commission": commission,
            }
            return
        new_qty = pos["qty"] + open_qty
        pos["entry_price"] = (pos["qty"] * pos["entry_price"] + open_qty * adj_price) / new_qty
        pos["entry_commission"] += commission
        pos["qty"] = new_qty
