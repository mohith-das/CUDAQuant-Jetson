"""Data quality gate tests.

Targets ``cudaquant.data.quality``: ``check_duplicates``,
``check_ohlc_validity``, ``check_negative_prices``, ``check_unsorted``.

Assumed convention: each check takes a DataFrame and returns a truthy value
when the data has the problem (or raises ``ValueError``); a falsy value for
clean data. Both conventions are accepted by the ``_caught`` helper, so an
implementation that raises on dirty input still passes — but a check that
silently accepts dirty data fails loudly.
"""

import pandas as pd
import pytest
from cudaquant.data.quality import (
    check_duplicates,
    check_negative_prices,
    check_ohlc_validity,
    check_unsorted,
)


def _clean_frame() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01", periods=4, freq="D")
    return pd.DataFrame(
        {
            "symbol": ["AAPL"] * 4,
            "timestamp": timestamps,
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [105.0, 106.0, 107.0, 108.0],
            "low": [99.0, 100.0, 101.0, 102.0],
            "close": [101.0, 102.0, 103.0, 104.0],
            "volume": [1000, 1100, 1200, 1300],
        }
    )


def _caught(fn, frame) -> bool:
    """True when the check flags the frame (truthy return or ValueError)."""
    try:
        return bool(fn(frame))
    except ValueError:
        return True


# ── check_duplicates ────────────────────────────────────────────────────────


def test_check_duplicates_detects_duplicates():
    frame = _clean_frame()
    frame = pd.concat([frame, frame.iloc[[1]]], ignore_index=True)
    assert _caught(check_duplicates, frame)


def test_check_duplicates_passes_clean_frame():
    assert not check_duplicates(_clean_frame())


def test_check_duplicates_ignores_unique_index_duplicate_values():
    """Duplicate values on distinct rows are not duplicate rows."""
    frame = _clean_frame()
    frame["close"] = [101.0, 101.0, 103.0, 104.0]
    assert not check_duplicates(frame)


# ── check_ohlc_validity ─────────────────────────────────────────────────────


def test_check_ohlc_validity_catches_high_below_low():
    frame = _clean_frame()
    frame.loc[2, "high"] = frame.loc[2, "low"] - 1.0
    assert _caught(check_ohlc_validity, frame)


def test_check_ohlc_validity_catches_high_below_close():
    frame = _clean_frame()
    frame.loc[1, "high"] = frame.loc[1, "close"] - 1.0
    assert _caught(check_ohlc_validity, frame)


def test_check_ohlc_validity_catches_low_above_open():
    frame = _clean_frame()
    frame.loc[0, "low"] = frame.loc[0, "open"] + 1.0
    assert _caught(check_ohlc_validity, frame)


def test_check_ohlc_validity_passes_clean_frame():
    assert not check_ohlc_validity(_clean_frame())


# ── check_negative_prices ───────────────────────────────────────────────────


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
def test_check_negative_prices_catches_negative(field):
    frame = _clean_frame()
    frame.loc[2, field] = -0.01
    assert _caught(check_negative_prices, frame)


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
def test_check_negative_prices_catches_zero(field):
    frame = _clean_frame()
    frame.loc[2, field] = 0.0
    assert _caught(check_negative_prices, frame)


def test_check_negative_prices_passes_clean_frame():
    assert not check_negative_prices(_clean_frame())


# ── check_unsorted ──────────────────────────────────────────────────────────


def test_check_unsorted_catches_shuffled_timestamps():
    frame = _clean_frame()
    frame = frame.sample(frac=1.0, random_state=1)  # shuffles rows
    assert _caught(check_unsorted, frame)


def test_check_unsorted_passes_sorted_frame():
    assert not check_unsorted(_clean_frame())


def test_check_unsorted_catches_reversed_order():
    frame = _clean_frame().iloc[::-1].reset_index(drop=True)
    assert _caught(check_unsorted, frame)
