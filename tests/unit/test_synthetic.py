"""Unit tests for the synthetic data generator.

Targets ``cudaquant.data.synthetic.SyntheticDataGenerator``.
"""

from datetime import datetime, timezone

import pandas as pd
import pytest

from cudaquant.data.schemas import BarFrequency
from cudaquant.data.synthetic import SyntheticDataGenerator

OHLCV_COLUMNS = {"open", "high", "low", "close", "volume"}


def _symbols_of(df: pd.DataFrame) -> set[str]:
    if "symbol" in df.columns:
        return set(df["symbol"])
    if "symbol" in df.index.names:
        return set(df.index.get_level_values("symbol"))
    raise AssertionError("generated data has no symbol column or index level")


def _groupby_symbol(df: pd.DataFrame):
    if "symbol" in df.columns:
        return df.groupby("symbol")
    if "symbol" in df.index.names:
        return df.groupby(level="symbol")
    raise AssertionError("generated data has no symbol column or index level")


@pytest.fixture
def generator() -> SyntheticDataGenerator:
    return SyntheticDataGenerator(seed=42)


@pytest.fixture
def sample_df(generator) -> pd.DataFrame:
    """Generate 1 day of 5-min bars for 2 symbols (~78 rows each)."""
    return generator.generate_bars(
        symbols=["AAPL", "MSFT"],
        start=datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, 16, 0, tzinfo=timezone.utc),
        frequency=BarFrequency.MINUTE_5,
    )


def test_columns_are_correct(sample_df):
    assert OHLCV_COLUMNS.issubset(set(sample_df.columns))
    assert "timestamp" in sample_df.columns
    assert "symbol" in sample_df.columns


def test_generate_bars_shape(sample_df):
    """Produces non-empty data with equal rows per symbol."""
    assert len(sample_df) > 0
    group_lens = [len(g) for _, g in _groupby_symbol(sample_df)]
    assert len(set(group_lens)) == 1  # all symbols have same bar count


def test_generate_bars_shape_single_symbol(generator):
    df = generator.generate_bars(
        symbols=["SPY"],
        start=datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
        frequency=BarFrequency.MINUTE_1,
    )
    assert len(df) > 0


def test_generate_bars_all_symbols_present(sample_df):
    assert _symbols_of(sample_df) == {"AAPL", "MSFT"}


def test_deterministic_same_seed_same_data():
    kwargs = dict(
        symbols=["AAPL"],
        start=datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
        frequency=BarFrequency.MINUTE_1,
    )
    a = SyntheticDataGenerator(seed=7).generate_bars(**kwargs)
    b = SyntheticDataGenerator(seed=7).generate_bars(**kwargs)
    pd.testing.assert_frame_equal(a, b)


def test_different_seed_different_data():
    kwargs = dict(
        symbols=["AAPL"],
        start=datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
        frequency=BarFrequency.MINUTE_1,
    )
    a = SyntheticDataGenerator(seed=1).generate_bars(**kwargs)
    b = SyntheticDataGenerator(seed=2).generate_bars(**kwargs)
    assert not a.equals(b)


def test_ohlc_relationships_valid(sample_df):
    assert (sample_df["high"] >= sample_df[["open", "close"]].max(axis=1)).all()
    assert (sample_df["low"] <= sample_df[["open", "close"]].min(axis=1)).all()
    assert (sample_df["high"] >= sample_df["low"]).all()
    assert (sample_df["volume"] >= 0).all()
    assert (sample_df["close"] > 0).all()


def test_timestamps_sorted_per_symbol(sample_df):
    for _, group in _groupby_symbol(sample_df):
        timestamps = pd.DatetimeIndex(group["timestamp"])
        assert timestamps.is_monotonic_increasing


def test_generate_scenarios_all_nonempty(generator):
    scenarios = generator.generate_scenarios()
    assert isinstance(scenarios, dict)
    assert len(scenarios) > 0
    for name, df in scenarios.items():
        assert len(df) > 0, f"scenario {name!r} produced no rows"
        assert OHLCV_COLUMNS.issubset(set(df.columns)), f"scenario {name!r} missing OHLCV columns"


def test_validate_bar_accepts_valid_bar(generator):
    bar = {
        "open": 100.0,
        "high": 105.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 1000,
        "timestamp": pd.Timestamp("2024-01-02 09:30:00"),
    }
    issues = generator.validate_bar(bar)
    assert issues == []  # empty list = valid


def _validate_rejects(generator, bar) -> bool:
    """True when validate_bar returns non-empty issue list."""
    return len(generator.validate_bar(bar)) > 0


def test_validate_bar_catches_negative_price(generator):
    bar = {
        "open": -100.0,
        "high": 105.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 1000,
        "timestamp": pd.Timestamp("2024-01-02 09:30:00"),
    }
    assert _validate_rejects(generator, bar)


def test_validate_bar_catches_invalid_ohlc(generator):
    bar = {
        "open": 100.0,
        "high": 90.0,  # high below low
        "low": 95.0,
        "close": 101.0,
        "volume": 1000,
        "timestamp": pd.Timestamp("2024-01-02 09:30:00"),
    }
    assert _validate_rejects(generator, bar)


def test_validate_bar_catches_negative_volume(generator):
    bar = {
        "open": 100.0,
        "high": 105.0,
        "low": 99.0,
        "close": 101.0,
        "volume": -5,
        "timestamp": pd.Timestamp("2024-01-02 09:30:00"),
    }
    assert _validate_rejects(generator, bar)


def test_different_symbols_produce_different_data(generator):
    df = generator.generate_bars(
        symbols=["AAPL", "MSFT"],
        start=datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
        frequency=BarFrequency.MINUTE_1,
    )
    aapl = df[df["symbol"] == "AAPL"]["close"].reset_index(drop=True)
    msft = df[df["symbol"] == "MSFT"]["close"].reset_index(drop=True)
    assert not aapl.equals(msft)
