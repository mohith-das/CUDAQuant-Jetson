"""Determinism, look-ahead, and metrics tests for the CPU backtester.

Targets the landed M1 implementation:
- ``cudaquant.backtest.engine.DeterministicBacktester`` with
  ``run(data, signal_fn, max_position_pct=0.10, long_only=True)`` returning
  ``{"equity_curve": list, "trades": list[dict], "metrics": dict}``.
  Data columns: ``symbol, timestamp, open, high, low, close, volume``.
- ``cudaquant.backtest.metrics.compute_metrics(equity_curve, trades,
  initial_capital, total_bars, volume_traded=None) -> dict``.

These tests are the executable spec for determinism and leakage safety. If the
backtester ever looks into the future, the look-ahead tests fail.
"""

import numpy as np
import pandas as pd
import pytest

from cudaquant.backtest.engine import DeterministicBacktester
from cudaquant.backtest.metrics import compute_metrics

SYMBOL = "AAPL"


def _frame(close: np.ndarray, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Build the engine's required (symbol, timestamp, OHLCV) layout."""
    open_ = close * 0.999
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    volume = np.full(len(close), 1_000.0)
    return pd.DataFrame(
        {
            "symbol": [SYMBOL] * len(close),
            "timestamp": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def _swing_data(bars: int = 300, seed: int = 0) -> pd.DataFrame:
    """Oscillating price (1.5 sine cycles) so momentum flips both ways and
    short positions both open and close, producing closed short trades."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=bars, freq="D")
    cycles = np.linspace(0.0, 3.0 * np.pi, bars)
    close = 100.0 * (1.0 + 0.08 * np.sin(cycles)) + 0.05 * rng.standard_normal(bars)
    return _frame(close, dates)


def _trend_data(bars: int = 200, seed: int = 0) -> pd.DataFrame:
    """Gentle monotonic uptrend; used for the equity-sanity bound."""
    dates = pd.date_range("2024-01-01", periods=bars, freq="D")
    close = 100.0 * np.linspace(1.0, 1.4, bars)
    return _frame(close, dates)


def _momentum_signal(df: pd.DataFrame) -> float:
    """21-bar momentum: +1 long, -1 short, 0 while warming up."""
    close = df["close"]
    if len(close) < 21:
        return 0.0
    return 1.0 if close.iloc[-1] > close.iloc[-21] else -1.0


def _buy_and_hold_signal(df: pd.DataFrame) -> float:
    return 1.0


def _run(backtester: DeterministicBacktester, data: pd.DataFrame, signal_fn=_momentum_signal, **kw):
    result = backtester.run(data, signal_fn, **kw)
    assert set(result) == {"equity_curve", "trades", "metrics"}, (
        "backtester result must expose equity_curve, trades, metrics"
    )
    return result


def _short_sides(trades) -> list[str]:
    return [t["side"] for t in trades if t.get("side") == "short"]


# ── Determinism ─────────────────────────────────────────────────────────────


def test_same_seed_same_data_identical_results():
    data = _swing_data(seed=3)
    r1 = _run(DeterministicBacktester(seed=42), data)
    r2 = _run(DeterministicBacktester(seed=42), data)
    assert r1["equity_curve"] == r2["equity_curve"]
    assert r1["trades"] == r2["trades"]
    assert r1["metrics"] == r2["metrics"]


def test_result_is_deterministic_across_instances():
    """Fresh instances with the same seed and data give bit-identical curves."""
    data = _swing_data(seed=5)
    a = _run(DeterministicBacktester(seed=7), data)
    b = _run(DeterministicBacktester(seed=7), data)
    assert a["equity_curve"] == b["equity_curve"]


def test_backtester_reacts_to_data_change():
    """Control: corrupting an EARLY bar must change results (test has teeth)."""
    data = _swing_data(seed=8)
    baseline = _run(DeterministicBacktester(seed=42), data)
    changed = data.copy()
    changed.loc[5, "close"] = changed.loc[5, "close"] * 2.0
    rerun = _run(DeterministicBacktester(seed=42), changed)
    assert rerun["equity_curve"] != baseline["equity_curve"]


# ── Look-ahead safety ───────────────────────────────────────────────────────


def test_no_lookahead_last_bar_change_does_not_affect_result():
    """Corrupt ONLY the final bar. No look-ahead ⇒ trades and the pre-final
    equity curve must be identical; the final equity mark may legitimately
    differ because open positions are marked to the corrupted close."""
    data = _swing_data(seed=3)
    baseline = _run(DeterministicBacktester(seed=42), data)

    corrupted = data.copy()
    last = len(corrupted) - 1
    corrupted.loc[last, "close"] *= 3.0
    corrupted.loc[last, "high"] *= 3.0
    rerun = _run(DeterministicBacktester(seed=42), corrupted)

    assert rerun["trades"] == baseline["trades"], "future bar affected trades (look-ahead!)"
    assert rerun["equity_curve"][:-1] == baseline["equity_curve"][:-1]


def test_no_lookahead_future_region_change_does_not_affect_result():
    """Corrupt the last 10 bars; everything before the corrupted region must
    produce an identical equity curve."""
    data = _swing_data(seed=5)
    baseline = _run(DeterministicBacktester(seed=42), data)

    corrupted = data.copy()
    corrupted.loc[len(corrupted) - 10 :, "close"] *= 0.25
    rerun = _run(DeterministicBacktester(seed=42), corrupted)

    common = len(baseline["equity_curve"]) - 10
    assert rerun["equity_curve"][:common] == baseline["equity_curve"][:common]


# ── long_only enforcement ───────────────────────────────────────────────────


def test_long_only_ignores_sell_signals():
    """The swing dataset must produce short trades when shorting is allowed;
    with long_only=True, no short position may ever be opened."""
    data = _swing_data(seed=11)
    unrestricted = _run(DeterministicBacktester(seed=42), data, long_only=False)
    restricted = _run(DeterministicBacktester(seed=42), data, long_only=True)

    assert _short_sides(unrestricted["trades"]), (
        "test fixture data did not generate short signals; long_only test "
        "would be vacuous"
    )
    assert _short_sides(restricted["trades"]) == [], (
        "long_only backtest opened a short position"
    )


def test_equity_never_drops_below_1_percent_of_initial():
    backtester = DeterministicBacktester(initial_capital=100_000.0)
    result = _run(backtester, _trend_data(seed=1), _buy_and_hold_signal)
    initial = 100_000.0
    assert min(result["equity_curve"]) >= initial * 0.99, (
        "equity fell more than 1% below starting capital"
    )


# ── Metrics ─────────────────────────────────────────────────────────────────


def _trade(pnl: float, entry: float = 100.0, exit: float = 110.0) -> dict:
    return {
        "entry_time": "2024-01-02T14:30:00Z",
        "exit_time": "2024-01-03T14:30:00Z",
        "symbol": SYMBOL,
        "side": "long",
        "entry_price": entry,
        "exit_price": exit,
        "qty": 10,
        "pnl": pnl,
        "return_pct": round(pnl / (10 * entry), 10),
        "exit_reason": "signal",
        "entry_idx": 0,
        "exit_idx": 1,
    }


def test_metrics_contract_keys_present():
    metrics = compute_metrics([100_000.0], [], 100_000.0, 1)
    assert {"total_return", "max_drawdown", "trade_count", "win_rate", "sharpe"}.issubset(
        set(metrics)
    )


def test_metrics_empty_trades_sensible_defaults():
    metrics = compute_metrics([100_000.0], [], 100_000.0, 1)
    assert metrics["total_return"] == 0.0
    assert metrics["trade_count"] == 0
    assert metrics["max_drawdown"] == 0.0
    assert metrics["win_rate"] == 0.0
    for key, value in metrics.items():
        if key != "profit_factor":  # may be inf by design when profit-only
            assert np.isfinite(value), f"non-finite metric: {key}={value!r}"


def test_metrics_single_winning_trade():
    metrics = compute_metrics([100_000.0, 110_000.0], [_trade(pnl=100.0)], 100_000.0, 2)
    assert metrics["trade_count"] == 1
    assert metrics["total_return"] == pytest.approx(0.10)
    assert metrics["win_rate"] == pytest.approx(1.0)


def test_metrics_single_losing_trade():
    metrics = compute_metrics([100_000.0, 99_000.0], [_trade(pnl=-100.0, exit=99.0)], 100_000.0, 2)
    assert metrics["trade_count"] == 1
    assert metrics["total_return"] == pytest.approx(-0.01)
    assert metrics["win_rate"] == pytest.approx(0.0)


def test_backtest_run_metrics_are_consistent_with_equity_curve():
    """The engine's own metrics must match the curve it produced."""
    result = _run(DeterministicBacktester(seed=42), _swing_data(seed=9))
    equity_curve = result["equity_curve"]
    metrics = result["metrics"]
    expected_total = (equity_curve[-1] - 100_000.0) / 100_000.0
    assert metrics["total_return"] == pytest.approx(expected_total)
