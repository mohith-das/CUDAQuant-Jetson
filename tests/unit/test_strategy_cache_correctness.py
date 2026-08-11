"""Regression test: strategy rolling-feature caching must key on data
identity, not just array length.

A length-only cache (`n != self._cached_len`) silently reuses stale
features if the same strategy instance is ever called with a different
DataFrame that happens to have the same row count — e.g. two different
backtests reusing one instance. Found via independent audit: reusing one
MeanReversion instance across two different 100-bar datasets produced 36
differing signals out of 100 versus a fresh instance on the same data.
"""

import numpy as np
import pandas as pd
import pytest

from cudaquant.strategies.implementations import IntradayMomentum, MeanReversion


@pytest.mark.parametrize("strategy_cls", [MeanReversion, IntradayMomentum])
def test_reused_instance_matches_fresh_instance_on_different_data(strategy_cls):
    rng1 = np.random.default_rng(1)
    rng2 = np.random.default_rng(2)
    data1 = pd.DataFrame({"close": 100 + np.cumsum(rng1.standard_normal(100))})
    data2 = pd.DataFrame({"close": 100 + np.cumsum(rng2.standard_normal(100))})

    reused = strategy_cls()
    reused.generate_signals(data1)
    signals_reused = reused.generate_signals(data2)

    fresh = strategy_cls()
    signals_fresh = fresh.generate_signals(data2)

    pd.testing.assert_series_equal(
        signals_reused,
        signals_fresh,
        check_names=False,
        obj=f"{strategy_cls.__name__} signals: reused instance vs fresh instance on same data2",
    )


@pytest.mark.parametrize("strategy_cls", [MeanReversion, IntradayMomentum])
def test_same_data_object_reuses_cache(strategy_cls):
    """Calling generate_signals twice with the SAME data object should hit
    the cache (same result, and the cached array must not be recomputed —
    verified indirectly by object identity of the cached array)."""
    rng = np.random.default_rng(3)
    data = pd.DataFrame({"close": 100 + np.cumsum(rng.standard_normal(50))})

    strat = strategy_cls()
    strat.generate_signals(data)
    cached_attr = "_cached_zscore" if strategy_cls is MeanReversion else "_cached_high"
    first_cache_array = getattr(strat, cached_attr)

    strat.generate_signals(data)
    second_cache_array = getattr(strat, cached_attr)

    assert first_cache_array is second_cache_array, (
        "cache was recomputed on a second call with the identical data object — "
        "the caching optimization isn't hitting when it should"
    )
