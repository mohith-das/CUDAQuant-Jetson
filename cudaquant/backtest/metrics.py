"""Backtest performance metrics.

``compute_metrics`` is a pure function: given an equity curve and a trade log
it produces every headline metric with no engine state. Edge cases (empty
trade list, single bar, zero volatility, non-positive capital) are handled
defensively and return deterministic zero values rather than raising.
"""

from __future__ import annotations

import math
from numbers import Integral

import numpy as np

TRADING_DAYS_PER_YEAR = 252


def compute_metrics(
    equity_curve: list[float],
    trades: list[dict],
    initial_capital: float,
    total_bars: int,
    volume_traded: float | None = None,
    bars_in_market: float | None = None,
) -> dict:
    """Compute all backtest metrics from an equity curve and trade log.

    Args:
        equity_curve: per-bar portfolio equity, marked to market at each bar's
            close. Assumed to be one bar per trading day for annualization.
        trades: list of closed-trade dicts. Each dict must contain
            ``qty``, ``entry_price``, ``exit_price``, ``pnl``, and ideally the
            bar-index fields ``entry_idx`` / ``exit_idx`` (used for
            holding-period metrics).
        initial_capital: starting capital.
        total_bars: total number of bars in the backtest.
        volume_traded: exact traded notional in currency. When omitted it is
            approximated from the trade log as ``qty * (entry + exit)`` per
            round trip, which is exact for the engine's trade granularity.
        bars_in_market: exact number of bars in which any position was held.
            When omitted, exposure is approximated from trade holding
            periods, which can overcount when partial fills produce
            overlapping sub-trades.

    Returns:
        A dict with the standard headline metrics (see keys below). All values
        are floats; ``profit_factor`` may be ``inf`` when there were profits
        but no losses.
    """
    curve = [float(x) for x in equity_curve]
    n_bars = len(curve)
    n_trades = len(trades)
    initial = float(initial_capital)

    # --- Return measures -------------------------------------------------
    total_return = 0.0
    if initial > 0 and n_bars:
        total_return = (curve[-1] - initial) / initial

    cagr = 0.0
    if initial > 0 and n_bars > 0 and curve[-1] > 0:
        years = n_bars / TRADING_DAYS_PER_YEAR
        if years > 0:
            cagr = (curve[-1] / initial) ** (1.0 / years) - 1.0

    # --- Risk-adjusted ratios --------------------------------------------
    returns = _bar_returns(curve)
    sharpe = _annualized_ratio(returns)
    sortino = _sortino_ratio(returns)

    # --- Drawdown ---------------------------------------------------------
    max_drawdown = _max_drawdown(curve)

    # --- Trade statistics --------------------------------------------------
    pnls = [float(t.get("pnl", 0.0)) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    win_rate = len(wins) / n_trades if n_trades else 0.0

    gross_profit = sum(wins)
    gross_loss = -sum(losses)  # positive magnitude
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = float("inf") if gross_profit > 0 else 0.0

    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean([-p for p in losses])) if losses else 0.0
    expectancy = avg_win * win_rate - avg_loss * (1.0 - win_rate)
    avg_trade = float(np.mean(pnls)) if pnls else 0.0

    # --- Turnover / exposure / holding period -----------------------------
    avg_equity = float(np.mean(curve)) if n_bars else 0.0
    if volume_traded is not None:
        traded_notional = float(volume_traded)
    else:
        traded_notional = float(
            sum(
                t.get("qty", 0) * (t.get("entry_price", 0.0) + t.get("exit_price", 0.0))
                for t in trades
            )
        )
    turnover = traded_notional / avg_equity if avg_equity > 0 else 0.0

    holding_periods = _holding_periods_bars(trades)
    if bars_in_market is not None:
        exposure = float(bars_in_market) / total_bars if total_bars > 0 else 0.0
    else:
        exposure = sum(holding_periods) / total_bars if total_bars > 0 else 0.0
    holding_period_avg = float(np.mean(holding_periods)) if holding_periods else 0.0

    return {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "turnover": turnover,
        "trade_count": n_trades,
        "avg_trade": avg_trade,
        "exposure": exposure,
        "holding_period_avg": holding_period_avg,
    }


def _bar_returns(curve: list[float]) -> list[float]:
    """Per-bar simple returns; zero when the previous equity is not positive."""
    returns = []
    for prev, cur in zip(curve, curve[1:], strict=False):
        returns.append(cur / prev - 1.0 if prev > 0 else 0.0)
    return returns


def _annualized_ratio(returns: list[float], annualization: int = TRADING_DAYS_PER_YEAR) -> float:
    """Sharpe-like ratio: mean/std * sqrt(annualization). Zero std -> 0.0."""
    if len(returns) < 2:
        return 0.0
    mean_r = float(np.mean(returns))
    std_r = float(np.std(returns, ddof=1))
    if not math.isfinite(std_r) or std_r == 0.0:
        return 0.0
    return mean_r / std_r * math.sqrt(annualization)


def _sortino_ratio(returns: list[float], annualization: int = TRADING_DAYS_PER_YEAR) -> float:
    """Sortino: mean / std(negative returns) * sqrt(annualization)."""
    if len(returns) < 2:
        return 0.0
    downside = [r for r in returns if r < 0]
    if len(downside) < 2:
        return 0.0
    mean_r = float(np.mean(returns))
    downside_std = float(np.std(downside, ddof=1))
    if not math.isfinite(downside_std) or downside_std == 0.0:
        return 0.0
    return mean_r / downside_std * math.sqrt(annualization)


def _max_drawdown(curve: list[float]) -> float:
    """Maximum peak-to-trough decline as a fraction of peak equity."""
    peak = -math.inf
    max_dd = 0.0
    for eq in curve:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def _holding_periods_bars(trades: list[dict]) -> list[int]:
    """Holding periods in bars from entry_idx/exit_idx, when available."""
    periods = []
    for t in trades:
        entry_idx = t.get("entry_idx")
        exit_idx = t.get("exit_idx")
        if isinstance(entry_idx, Integral) and isinstance(exit_idx, Integral) and exit_idx >= entry_idx:
            periods.append(int(exit_idx - entry_idx))
    return periods
