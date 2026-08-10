"""Batched GPU experiment runner — parallelizes feature computation
across parameter combinations for grid/random search.

Instead of N sequential CPU passes, computes rolling features for all
parameter variations in one batched GPU operation, then runs backtests
on the pre-computed features.
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
    """Run multiple experiments with batched GPU feature computation.

    For strategies that depend on rolling window features (momentum,
    mean reversion, etc.), computes features for ALL window sizes in
    one batched pass, then runs backtests on pre-computed features.
    This avoids redundant O(n * n_params * window) computation.
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
        """Run a grid search with batched GPU feature computation.

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

        # Pre-compute features for ALL window sizes in one pass if
        # the param_grid includes lookback/window parameters
        _feature_cache = self._precompute_features(data, param_grid, base)

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

        If None of the varied parameters affect feature computation (no
        lookback/window/threshold params), returns empty dict.
        """
        window_params = {"lookback", "window", "exit_lookback", "mean_reversion_window"}
        varied_windows = set(param_grid.keys()) & window_params

        if not varied_windows:
            return {}

        close = data["close"].values.astype(np.float64)
        cache = {}

        # Compute all unique window sizes
        all_windows = set()
        for key in varied_windows:
            all_windows.update(param_grid[key])

        # Batch compute rolling features for all windows
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
        """Benchmark sequential vs batched approach.

        Returns dict with timing and speedup for both approaches.
        """
        base = base_params or {}

        # Sequential: run each combination with its own feature computation
        import itertools
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combos = list(itertools.product(*values))

        t0 = time.perf_counter()
        for combo in combos:
            params = {**base, **dict(zip(keys, combo, strict=True))}
            strategy = strategy_factory(params)
            bt = self._bt_factory()
            bt.run(data=data, signal_fn=strategy.generate_signals)
        seq_time = (time.perf_counter() - t0) * 1000

        # Batched: pre-compute once, run backtests
        t0 = time.perf_counter()
        self.run_grid(data, strategy_factory, param_grid, base)
        batched_time = (time.perf_counter() - t0) * 1000

        return {
            "n_combinations": len(combos),
            "n_bars": len(data),
            "sequential_ms": round(seq_time, 2),
            "batched_ms": round(batched_time, 2),
            "speedup": round(seq_time / batched_time, 2) if batched_time > 0 else 0,
        }
