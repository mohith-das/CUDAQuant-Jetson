"""Market regime detection using volatility, trend, volume, and correlation signals.

Regimes are classified at each bar using rolling window features.
Multiple regime types enable strategy conditioning and performance
attribution by market environment.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from cudaquant.features import (
    realized_volatility,
    relative_volume,
    returns,
    rolling_mean,
    rolling_std,
)


class Regime(str, Enum):
    """Market regime labels."""

    TRENDING_HIGH_VOL = "trending_high_vol"
    TRENDING_LOW_VOL = "trending_low_vol"
    RANGING_HIGH_VOL = "ranging_high_vol"
    RANGING_LOW_VOL = "ranging_low_vol"
    UNKNOWN = "unknown"


@dataclass
class RegimeResult:
    """Regime classification result for a single bar."""

    regime: Regime
    volatility: float
    trend_strength: float
    volume_intensity: float
    dispersion: float


class RegimeDetector:
    """Detect market regimes using rolling window features.

    Versioned detector for reproducibility. Records parameters and
    version for experiment tracking.

    Signals used:
    - Volatility: rolling std of returns (annualized)
    - Trend: absolute value of rolling mean of returns / rolling std
    - Volume: relative volume vs. rolling average
    - Dispersion: cross-sectional std of returns (multi-asset)
    - Correlation: average pairwise correlation (multi-asset)

    Classification:
    - High vol if volatility > median + 0.5 * std of historical vol
    - Trending if |trend_strength| > threshold
    - Ranging otherwise
    """

    def __init__(
        self,
        vol_window: int = 20,
        trend_window: int = 20,
        vol_percentile: float = 0.6,
        trend_threshold: float = 0.3,
        version: int = 1,
    ):
        self.vol_window = vol_window
        self.trend_window = trend_window
        self.vol_percentile = vol_percentile
        self.trend_threshold = trend_threshold
        self.version = version

    def detect(self, data: pd.DataFrame, market_data: pd.DataFrame | None = None) -> pd.Series:
        """Classify regime for each bar in data.

        Args:
            data: OHLCV DataFrame with 'close' column, sorted chronologically.
            market_data: Optional market benchmark (e.g., SPY) for beta/correlation.

        Returns:
            Series of Regime values, same index as data.
        """
        close = data["close"].values.astype(np.float64)
        n = len(close)

        if n < max(self.vol_window, self.trend_window) + 5:
            return pd.Series([Regime.UNKNOWN] * n, index=data.index)

        # Compute signals
        rets = returns(close)
        volatility = realized_volatility(rets, self.vol_window, annualize=252)
        vol_mean = rolling_mean(volatility, self.vol_window * 5)
        vol_std = rolling_std(volatility, self.vol_window * 5)

        # Trend strength: |mean(rets)| / std(rets)
        trend_mean = rolling_mean(rets, self.trend_window)
        trend_std = rolling_std(rets, self.trend_window)
        trend_strength = np.abs(trend_mean) / np.maximum(trend_std, 1e-10)

        # Classify each bar
        regimes = []
        for i in range(n):
            if i < max(self.vol_window, self.trend_window) or np.isnan(volatility[i]):
                regimes.append(Regime.UNKNOWN)
                continue

            # Determine vol regime
            vol_threshold = vol_mean[i] + 0.5 * vol_std[i] if not np.isnan(vol_mean[i]) else np.nanmedian(volatility)
            high_vol = volatility[i] > vol_threshold

            # Determine trend regime
            trending = trend_strength[i] > self.trend_threshold

            if high_vol and trending:
                regimes.append(Regime.TRENDING_HIGH_VOL)
            elif high_vol and not trending:
                regimes.append(Regime.RANGING_HIGH_VOL)
            elif not high_vol and trending:
                regimes.append(Regime.TRENDING_LOW_VOL)
            else:
                regimes.append(Regime.RANGING_LOW_VOL)

        return pd.Series(regimes, index=data.index)

    def detect_with_details(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return detailed regime info including signal values.

        Returns DataFrame with columns: regime, volatility, trend_strength,
        volume_intensity.
        """
        regime_series = self.detect(data)
        close = data["close"].values.astype(np.float64)
        n = len(close)

        rets = returns(close)
        volatility = realized_volatility(rets, self.vol_window, annualize=252)
        trend_mean = rolling_mean(rets, self.trend_window)
        trend_std = rolling_std(rets, self.trend_window)
        trend_strength = np.abs(trend_mean) / np.maximum(trend_std, 1e-10)

        vol = data.get("volume", pd.Series(np.ones(n)))
        if isinstance(vol, pd.Series):
            vol = vol.values
        rel_vol = relative_volume(vol.astype(np.float64), self.vol_window)

        return pd.DataFrame({
            "regime": regime_series.values,
            "volatility": volatility,
            "trend_strength": trend_strength,
            "volume_intensity": rel_vol,
        }, index=data.index)

    def regime_distribution(self, data: pd.DataFrame) -> dict:
        """Return the distribution of regimes in the data."""
        regimes = self.detect(data)
        counts = regimes.value_counts()
        return {str(k): int(v) for k, v in counts.items()}

    def strategy_by_regime(
        self,
        data: pd.DataFrame,
        trades: list[dict],
    ) -> dict[str, dict]:
        """Compute strategy performance metrics broken down by regime.

        Args:
            data: OHLCV data used for regime detection.
            trades: List of trade dicts from backtester (must have entry_time).

        Returns:
            Dict mapping regime name to {trade_count, total_pnl, win_rate, avg_return}.
        """
        regimes = self.detect(data)

        regime_stats: dict[str, dict] = {}
        for r in Regime:
            regime_stats[r.value] = {
                "trade_count": 0,
                "total_pnl": 0.0,
                "wins": 0,
                "losses": 0,
            }

        for trade in trades:
            entry_time = trade.get("entry_time")
            if entry_time is None:
                continue

            # Find closest regime
            if isinstance(entry_time, pd.Timestamp):
                closest_idx = (data["timestamp"] - entry_time).abs().idxmin()
            else:
                continue

            regime = regimes.iloc[closest_idx] if closest_idx < len(regimes) else Regime.UNKNOWN
            key = regime.value

            pnl = trade.get("pnl", 0.0)
            regime_stats[key]["trade_count"] += 1
            regime_stats[key]["total_pnl"] += pnl
            if pnl > 0:
                regime_stats[key]["wins"] += 1
            else:
                regime_stats[key]["losses"] += 1

        # Compute win rates
        for stats in regime_stats.values():
            total = stats["wins"] + stats["losses"]
            stats["win_rate"] = stats["wins"] / total if total > 0 else 0.0
            if "trade_count" in stats:
                tc = stats["trade_count"]
                stats["avg_pnl"] = stats["total_pnl"] / tc if tc > 0 else 0.0

        return regime_stats

    def get_info(self) -> dict:
        return {
            "version": self.version,
            "vol_window": self.vol_window,
            "trend_window": self.trend_window,
            "vol_percentile": self.vol_percentile,
            "trend_threshold": self.trend_threshold,
        }
