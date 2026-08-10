"""Feature engineering — CPU reference implementations and GPU dispatch.

All consumers should import from cudaquant.features (this package) to
automatically get the fastest backend via the dispatch layer.
"""

from cudaquant.features.dispatch import (
    atr,
    distance_from_high,
    distance_from_low,
    market_relative_return,
    momentum,
    overnight_gap,
    realized_volatility,
    relative_volume,
    returns,
    rolling_beta,
    rolling_correlation,
    rolling_max,
    rolling_mean,
    rolling_min,
    rolling_std,
    rolling_sum,
    rolling_variance,
    rolling_zscore,
    rsi,
    time_of_day_encoding,
    volume_zscore,
    vwap,
    vwap_deviation,
)

__all__ = [
    "atr",
    "distance_from_high",
    "distance_from_low",
    "market_relative_return",
    "momentum",
    "overnight_gap",
    "realized_volatility",
    "relative_volume",
    "returns",
    "rolling_beta",
    "rolling_correlation",
    "rolling_max",
    "rolling_mean",
    "rolling_min",
    "rolling_std",
    "rolling_sum",
    "rolling_variance",
    "rolling_zscore",
    "rsi",
    "time_of_day_encoding",
    "volume_zscore",
    "vwap",
    "vwap_deviation",
]
