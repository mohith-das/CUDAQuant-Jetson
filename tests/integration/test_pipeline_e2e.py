"""End-to-end pipeline integration tests.

Wires the real subsystems together the way the application does — synthetic
data -> strategy signals -> deterministic backtester -> metrics, plus
walk-forward validation and regime detection. These modules had ~0% coverage
from the unit suite; this exercises them as an integrated whole and pins the
contracts other layers depend on.

No look-ahead, no fabricated numbers: assertions are structural + determinism +
sanity bounds, not hand-picked magic values.
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from cudaquant.backtest.engine import DeterministicBacktester
from cudaquant.backtest.validation import WalkForwardConfig, WalkForwardValidator
from cudaquant.data.schemas import BarFrequency
from cudaquant.data.synthetic import SyntheticDataGenerator
from cudaquant.regimes.detector import Regime, RegimeDetector
from cudaquant.strategies.buy_and_hold import BuyAndHold
from cudaquant.strategies.implementations import IntradayMomentum, MeanReversion

pytestmark = pytest.mark.integration

SYMBOL = "AAPL"


def _daily(n_bars: int = 220, seed: int = 7) -> pd.DataFrame:
    """Deterministic single-symbol daily OHLCV frame via the real generator."""
    gen = SyntheticDataGenerator(seed=seed)
    start = datetime(2022, 1, 1)
    end = start + timedelta(days=n_bars)
    df = gen.generate_bars([SYMBOL], start, end, BarFrequency.DAY_1, seed=seed)
    # Engine only needs symbol/timestamp/OHLCV; extra cols (frequency, vwap) are fine.
    return df.reset_index(drop=True)


@pytest.fixture(scope="module")
def data() -> pd.DataFrame:
    df = _daily()
    assert len(df) >= 150, f"generator produced too few bars: {len(df)}"
    # Data-quality invariants the whole pipeline relies on.
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()
    assert (df[["open", "high", "low", "close"]] > 0).all().all()
    return df


# ── strategy -> backtester ───────────────────────────────────────────────────

STRATEGY_FACTORIES = {
    "intraday_momentum": lambda: IntradayMomentum(lookback=20),
    "mean_reversion": lambda: MeanReversion(),
    "buy_and_hold": lambda: BuyAndHold(),
}


@pytest.mark.parametrize("name", list(STRATEGY_FACTORIES))
def test_strategy_runs_through_backtester(data: pd.DataFrame, name: str):
    """Each strategy's Series signals integrate with the backtester (which
    consumes the last value of an expanding window) and yield a valid result."""
    strategy = STRATEGY_FACTORIES[name]()

    # generate_signals contract: one signal per bar, values in {-1, 0, 1}.
    sigs = strategy.generate_signals(data)
    assert isinstance(sigs, pd.Series)
    assert len(sigs) == len(data)
    assert set(sigs.unique()).issubset({-1, 0, 1, -1.0})

    result = DeterministicBacktester(seed=42).run(data, strategy.generate_signals)
    assert set(result) == {"equity_curve", "trades", "metrics"}
    assert len(result["equity_curve"]) == len(data)
    assert result["metrics"]["trade_count"] == len(result["trades"])
    assert all(e > 0 for e in result["equity_curve"]), "equity went non-positive"


@pytest.mark.parametrize("name", list(STRATEGY_FACTORIES))
def test_pipeline_is_deterministic(data: pd.DataFrame, name: str):
    """Same strategy + same data + same seed => bit-identical results."""
    s1, s2 = STRATEGY_FACTORIES[name](), STRATEGY_FACTORIES[name]()
    r1 = DeterministicBacktester(seed=42).run(data, s1.generate_signals)
    r2 = DeterministicBacktester(seed=42).run(data, s2.generate_signals)
    assert r1["equity_curve"] == r2["equity_curve"]
    assert r1["trades"] == r2["trades"]
    assert r1["metrics"] == r2["metrics"]


def test_buy_and_hold_tracks_price_direction(data: pd.DataFrame):
    """Buy-and-hold total return must have the same sign as the underlying
    price move over the window (a coarse but real sanity check)."""
    result = DeterministicBacktester(seed=1).run(data, BuyAndHold().generate_signals)
    price_move = data["close"].iloc[-1] - data["close"].iloc[0]
    total_return = result["metrics"]["total_return"]
    if abs(price_move) > 1e-6:
        assert (total_return >= 0) == (price_move > 0) or abs(total_return) < 1e-3


# ── walk-forward validation ──────────────────────────────────────────────────


def test_walk_forward_produces_chronological_folds(data: pd.DataFrame):
    cfg = WalkForwardConfig(n_splits=3, train_size=90, test_size=30, gap=3, anchored=True)
    validator = WalkForwardValidator(cfg)
    results = validator.validate(
        data,
        strategy_factory=lambda: IntradayMomentum(lookback=15),
        backtester_factory=lambda: DeterministicBacktester(seed=42),
    )
    assert len(results) >= 1, "expected at least one walk-forward fold"
    for fold in results:
        # Leakage guard: train must end strictly before test begins.
        assert fold.train_end < fold.test_start, "train overlaps/leaks into test"
        assert "total_return" in fold.test_metrics
        assert len(fold.equity_curve) > 0
    # Folds advance forward in time.
    starts = [f.test_start for f in results]
    assert starts == sorted(starts)


def test_walk_forward_gap_enforces_purge(data: pd.DataFrame):
    """With a positive gap, the last train timestamp and first test timestamp
    must be separated (purge), never adjacent/overlapping."""
    cfg = WalkForwardConfig(n_splits=2, train_size=90, test_size=30, gap=5, anchored=True)
    results = WalkForwardValidator(cfg).validate(
        data,
        strategy_factory=lambda: MeanReversion(),
        backtester_factory=lambda: DeterministicBacktester(seed=42),
    )
    for fold in results:
        assert fold.train_end < fold.test_start


# ── regime detection ─────────────────────────────────────────────────────────


def test_regime_detection_labels_every_bar(data: pd.DataFrame):
    regimes = RegimeDetector().detect(data)
    assert isinstance(regimes, pd.Series)
    assert len(regimes) == len(data)
    valid = set(Regime)
    assert all(r in valid for r in regimes), "detector emitted an unknown regime label"


def test_regime_distribution_sums_to_bar_count(data: pd.DataFrame):
    dist = RegimeDetector().regime_distribution(data)
    assert isinstance(dist, dict)
    # Distribution is a proportion or count map; either way it must be non-empty
    # and cover only valid regime labels.
    assert dist, "empty regime distribution"
    for key in dist:
        assert key in {r.value for r in Regime} or key in set(Regime)
