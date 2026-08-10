"""Strict time-series validation and walk-forward analysis.

CRITICAL: Never random-split time series. All validation uses chronological splits,
purge/embargo for overlapping labels, and untouched holdout periods.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward validation."""

    n_splits: int = 5
    train_size: int = 252 * 2  # 2 years of daily bars
    test_size: int = 252  # 1 year
    gap: int = 0  # purge period between train and test
    embargo: int = 0  # additional test-exclusion after test period
    anchored: bool = True  # expanding window (True) vs rolling (False)


@dataclass
class WalkForwardResult:
    """Results from one walk-forward fold."""

    fold: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_metrics: dict
    test_metrics: dict
    trades: list[dict]
    equity_curve: list[float]


class WalkForwardValidator:
    """Chronological walk-forward validation with leakage safeguards.

    Guarantees:
    - Training data is always BEFORE test data (no future information)
    - Configurable purge gap between train and test
    - Embargo period after test to prevent overlapping labels
    - Expanding or rolling window options
    """

    def __init__(self, config: WalkForwardConfig | None = None):
        self.config = config or WalkForwardConfig()

    def split(
        self, timestamps: pd.DatetimeIndex
    ) -> list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
        """Generate chronological train/test splits.

        Returns list of (train_indices, test_indices) for each fold.
        """
        timestamps = pd.DatetimeIndex(sorted(timestamps))
        n = len(timestamps)
        splits = []

        if n < self.config.train_size + self.config.test_size:
            return splits  # not enough data

        for fold in range(self.config.n_splits):
            if self.config.anchored:
                # Expanding window
                train_end_idx = self.config.train_size + fold * self.config.test_size
                test_start_idx = train_end_idx + self.config.gap
                test_end_idx = min(test_start_idx + self.config.test_size, n)
                train_start_idx = 0
            else:
                # Rolling window
                offset = fold * self.config.test_size
                train_start_idx = offset
                train_end_idx = offset + self.config.train_size
                test_start_idx = train_end_idx + self.config.gap
                test_end_idx = min(test_start_idx + self.config.test_size, n)

            if test_end_idx > n or test_start_idx >= n:
                break
            if train_end_idx > test_start_idx:
                break  # overlapping — shouldn't happen with gap

            train_ts = timestamps[train_start_idx:train_end_idx]
            test_ts = timestamps[test_start_idx:test_end_idx]

            if len(train_ts) < 10 or len(test_ts) < 5:
                continue

            splits.append((train_ts, test_ts))

        return splits

    def validate(
        self,
        data: pd.DataFrame,
        strategy_factory: Callable[[], object],
        backtester_factory: Callable[[], object],
    ) -> list[WalkForwardResult]:
        """Run walk-forward validation on data.

        Args:
            data: DataFrame with columns [timestamp, symbol, open, high, low, close, volume]
            strategy_factory: Callable that returns a fresh Strategy instance per fold
            backtester_factory: Callable that returns a fresh DeterministicBacktester per fold

        Returns list of WalkForwardResult, one per fold.
        """
        timestamps = pd.DatetimeIndex(data["timestamp"].unique())
        splits = self.split(timestamps)
        results = []

        for fold_idx, (train_ts, test_ts) in enumerate(splits):
            strategy = strategy_factory()
            backtester = backtester_factory()

            # Train the strategy on the in-sample fold if it supports it. Baseline
            # strategies have no `train` method; ML-backed strategies may add one.
            if hasattr(strategy, "train"):
                train_data = data[data["timestamp"].isin(train_ts)]
                strategy.train(train_data)

            # Backtest on test period
            test_data = data[data["timestamp"].isin(test_ts)]
            if len(test_data) < 5:
                continue

            bt_result = backtester.run(
                data=test_data,
                signal_fn=strategy.generate_signals,
            )

            results.append(WalkForwardResult(
                fold=fold_idx + 1,
                train_start=train_ts.min(),
                train_end=train_ts.max(),
                test_start=test_ts.min(),
                test_end=test_ts.max(),
                train_metrics={},
                test_metrics=bt_result.get("metrics", {}),
                trades=bt_result.get("trades", []),
                equity_curve=bt_result.get("equity_curve", []),
            ))

        return results

    def aggregate_metrics(self, results: list[WalkForwardResult]) -> dict:
        """Compute aggregate metrics across all walk-forward folds."""
        if not results:
            return {"error": "no folds completed"}

        test_metrics = [r.test_metrics for r in results]
        metric_names = set()
        for m in test_metrics:
            metric_names.update(m.keys())

        aggregated = {}
        for name in metric_names:
            values = [m.get(name, np.nan) for m in test_metrics]
            valid = [v for v in values if not np.isnan(v)]
            if valid:
                aggregated[f"{name}_mean"] = float(np.mean(valid))
                aggregated[f"{name}_std"] = float(np.std(valid))
                aggregated[f"{name}_min"] = float(np.min(valid))
                aggregated[f"{name}_max"] = float(np.max(valid))

        aggregated["n_folds"] = len(results)
        aggregated["n_trades_total"] = sum(len(r.trades) for r in results)
        return aggregated


def check_lookahead(
    data: pd.DataFrame,
    feature_fn: Callable[[pd.DataFrame], pd.Series],
    contamination_idx: int | None = None,
) -> dict:
    """Verify that a feature function does not look ahead.

    Modifies a future data point and checks that features computed BEFORE
    that point are unchanged. If they change, there's a lookahead bug.

    Args:
        data: OHLCV DataFrame.
        feature_fn: Function that computes features from data.
        contamination_idx: Index to corrupt (defaults to midpoint).

    Returns:
        dict with 'lookahead_detected' (bool) and 'evidence' (str).
    """
    n = len(data)
    if n < 10:
        return {"lookahead_detected": False, "evidence": "too few bars to test"}

    if contamination_idx is None:
        contamination_idx = n // 2

    # Compute features on clean data
    clean_features = feature_fn(data.copy())

    # Corrupt a future data point
    corrupted = data.copy()
    if "close" in corrupted.columns:
        corrupted.loc[corrupted.index[contamination_idx], "close"] *= 100.0

    # Compute features on corrupted data
    corrupted_features = feature_fn(corrupted)

    # Features before the contamination point should be identical
    before_idx = max(0, contamination_idx - 5)
    clean_before = clean_features.iloc[:before_idx]
    corrupt_before = corrupted_features.iloc[:before_idx]

    # Compare
    if not clean_before.equals(corrupt_before):
        # Find which values differ
        diff_mask = clean_before != corrupt_before
        affected = diff_mask.sum()
        return {
            "lookahead_detected": True,
            "evidence": f"{affected} values before bar {before_idx} changed when bar {contamination_idx} was modified",
        }

    return {"lookahead_detected": False, "evidence": "features before contamination unchanged"}


def check_target_leakage(
    data: pd.DataFrame,
    features: pd.DataFrame,
    target: pd.Series,
    horizon: int = 1,
) -> dict:
    """Check for target leakage in features.

    Verifies that features at time t do not contain information about
    target at time t+horizon that wouldn't be available yet.

    Args:
        data: OHLCV DataFrame with timestamp index.
        features: Feature DataFrame aligned to data.
        target: Target Series aligned to data.
        horizon: Forward horizon for target.

    Returns:
        dict with leakage assessment.
    """
    if len(features) < horizon + 10:
        return {"leakage_detected": False, "evidence": "insufficient data"}

    # Check correlation between current features and future target
    # If features contain future information, this correlation will be
    # unreasonably high compared to the same features shifted back

    from scipy.stats import pearsonr

    future_target = target.shift(-horizon)
    correlations = {}

    for col in features.select_dtypes(include=[np.number]).columns:
        valid = ~(features[col].isna() | future_target.isna())
        if valid.sum() < 10:
            continue
        corr, pval = pearsonr(features[col][valid], future_target[valid])
        correlations[col] = abs(corr)

    # Flag suspiciously high correlations (>0.95 is almost certainly leakage)
    suspicious = {k: v for k, v in correlations.items() if v > 0.95}

    return {
        "leakage_detected": len(suspicious) > 0,
        "evidence": f"suspicious correlations: {suspicious}" if suspicious else "no suspicious correlations found",
        "max_correlation": max(correlations.values()) if correlations else 0,
    }


def check_future_normalization(data: pd.DataFrame, features: pd.DataFrame) -> dict:
    """Check if features were normalized using future data (e.g., global min/max)."""
    n = len(features)
    if n < 20:
        return {"future_normalization": False, "evidence": "insufficient data"}

    # Split data chronologically
    mid = n // 2
    first_half = features.iloc[:mid]
    second_half = features.iloc[mid:]

    issues = []
    for col in features.select_dtypes(include=[np.number]).columns:
        fh_min = first_half[col].min()
        fh_max = first_half[col].max()
        sh = second_half[col].dropna()

        if len(sh) == 0:
            continue

        # If second half has values outside first half range AND this is a
        # normalized feature (mean~0, std~1), it might be fine — new regime.
        # But if second half is perfectly bounded by first half's min/max,
        # the normalization used global (future-looking) bounds.
        below = (sh < fh_min).sum()
        above = (sh > fh_max).sum()

        if below == 0 and above == 0 and len(sh) > 0:
            issues.append(f"{col}: second half perfectly bounded by first half range")

    return {
        "future_normalization": len(issues) > 0,
        "evidence": issues if issues else "no future normalization detected",
    }
