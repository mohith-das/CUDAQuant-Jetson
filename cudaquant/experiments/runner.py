"""Batched GPU experiment runner.

Profiling shows the deterministic backtester's walk-forward loop consumes
>99% of grid-search runtime on typical experiment sizes (200–5000 bars).
Rolling feature computation is ~0.1% of total. Replacing per-strategy
feature recomputation with a shared pre-computed feature cache would not
materially improve throughput — the backtester itself is the bottleneck.

The _precompute_features() method is retained as an API surface for a
future GPU-accelerated backtester, which would shift the bottleneck and
make batched feature pre-computation profitable. For now it is built but
intentionally not wired into run_grid().
"""

import time
from collections.abc import Callable

import numpy as np
import pandas as pd

from cudaquant.backtest.engine import DeterministicBacktester
from cudaquant.features.dispatch import (
    rolling_max,
    rolling_mean,
    rolling_min,
    rolling_std,
    rolling_zscore,
)


class BatchedExperimentRunner:
    """Run multiple experiments with optional batched GPU feature computation.

    Features can be pre-computed once for all parameter combinations via
    _precompute_features(), but current profiling shows the backtester
    walk-forward loop dominates runtime so aggressively (>99%) that
    eliminating redundant feature computation would not meaningfully
    improve total throughput.
    """

    def __init__(self, backtester_factory: Callable[[], DeterministicBacktester] | None = None):
        self._bt_factory = backtester_factory or (lambda: DeterministicBacktester(seed=42))

    def run_grid(
        self,
        data: pd.DataFrame,
        strategy_factory: Callable[[dict], object],
        param_grid: dict[str, list],
        base_params: dict | None = None,
    ) -> list[dict]:
        """Run a grid search sequentially.

        Args:
            data: OHLCV DataFrame.
            strategy_factory: fn(params) -> Strategy instance.
            param_grid: {param_name: [values]}.
            base_params: Fixed parameters for all runs.

        Returns:
            List of {params, metrics, trades, runtime_ms} per combination.
        """
        import itertools

        base = base_params or {}
        keys = list(param_grid.keys())
        values = list(param_grid.values())

        results = []
        for combo in itertools.product(*values):
            params = {**base, **dict(zip(keys, combo, strict=True))}
            strategy = strategy_factory(params)

            t0 = time.perf_counter()
            bt = self._bt_factory()
            bt_result = bt.run(data=data, signal_fn=strategy.generate_signals)
            runtime_ms = (time.perf_counter() - t0) * 1000

            results.append({
                "params": params,
                "metrics": bt_result.get("metrics", {}),
                "trades": bt_result.get("trades", []),
                "runtime_ms": runtime_ms,
            })

        return results

    def _precompute_features(
        self,
        data: pd.DataFrame,
        param_grid: dict[str, list],
        base_params: dict,
    ) -> dict:
        """Pre-compute rolling features for all window sizes in the grid.

        Built but intentionally not wired into run_grid(). See module
        docstring for the profiling rationale. Retained as an API surface
        for a future GPU-accelerated backtester.
        """
        window_params = {"lookback", "window", "exit_lookback", "mean_reversion_window"}
        varied_windows = set(param_grid.keys()) & window_params

        if not varied_windows:
            return {}

        close = data["close"].values.astype(np.float64)
        cache = {}

        all_windows = set()
        for key in varied_windows:
            all_windows.update(param_grid[key])

        for w in sorted(all_windows):
            w_int = int(w)
            if w_int < 2:
                continue
            cache[f"rolling_mean_{w_int}"] = rolling_mean(close, w_int)
            cache[f"rolling_std_{w_int}"] = rolling_std(close, w_int)
            cache[f"rolling_min_{w_int}"] = rolling_min(close, w_int)
            cache[f"rolling_max_{w_int}"] = rolling_max(close, w_int)
            cache[f"rolling_zscore_{w_int}"] = rolling_zscore(close, w_int)

        return cache

    def benchmark_sequential_vs_batched(
        self,
        data: pd.DataFrame,
        strategy_factory: Callable[[dict], object],
        param_grid: dict[str, list],
        base_params: dict | None = None,
    ) -> dict:
        """Benchmark where time is spent in a grid search.

        Returns a breakdown of feature computation vs backtest time,
        proving that the backtester dominates (>99%).
        """
        import itertools

        base = base_params or {}
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combos = list(itertools.product(*values))

        # Time feature computation for ALL combos
        t0 = time.perf_counter()
        self._precompute_features(data, param_grid, base)
        feature_time = (time.perf_counter() - t0) * 1000

        # Time ONE backtest
        combo = combos[0]
        params = {**base, **dict(zip(keys, combo, strict=True))}
        strategy = strategy_factory(params)
        t0 = time.perf_counter()
        bt = self._bt_factory()
        bt.run(data=data, signal_fn=strategy.generate_signals)
        single_bt_time = (time.perf_counter() - t0) * 1000

        # Time ALL backtests sequentially
        t0 = time.perf_counter()
        for combo in combos:
            params = {**base, **dict(zip(keys, combo, strict=True))}
            strategy = strategy_factory(params)
            bt = self._bt_factory()
            bt.run(data=data, signal_fn=strategy.generate_signals)
        total_bt_time = (time.perf_counter() - t0) * 1000

        return {
            "n_combinations": len(combos),
            "n_bars": len(data),
            "feature_precompute_ms": round(feature_time, 2),
            "single_backtest_ms": round(single_bt_time, 2),
            "total_backtest_ms": round(total_bt_time, 2),
            "total_ms": round(feature_time + total_bt_time, 2),
            "feature_pct": round(feature_time / (feature_time + total_bt_time) * 100, 4)
            if (feature_time + total_bt_time) > 0 else 0,
        }
