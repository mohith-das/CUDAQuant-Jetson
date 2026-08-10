"""Synthetic market data generator with realistic OHLCV bar scenarios."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from cudaquant.data.schemas import Bar, BarFrequency


class SyntheticDataGenerator:
    """Generate realistic synthetic OHLCV bar data with multiple market scenarios.

    Uses seeded numpy RNG for full reproducibility.
    """

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = np.random.default_rng(seed)

    def generate_bars(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: BarFrequency,
        seed: int | None = None,
    ) -> pd.DataFrame:
        """Generate OHLCV bars for multiple symbols over a date range.

        Returns DataFrame with columns: symbol, timestamp, open, high, low, close,
        volume, frequency, vwap.
        """
        rng = np.random.default_rng(seed if seed is not None else self._seed)
        freq_minutes = self._freq_to_minutes(frequency)
        total_minutes = int((end - start).total_seconds() / 60)
        n_bars = total_minutes // freq_minutes
        if n_bars < 1:
            n_bars = 1

        timestamps = pd.date_range(start=start, periods=n_bars, freq=f"{freq_minutes}min", tz="UTC")

        all_rows = []
        for symbol in symbols:
            # Random walk with drift for close prices
            drift = rng.uniform(-0.0002, 0.0005)  # slight upward bias
            volatility = rng.uniform(0.005, 0.02)
            close_prices = self._random_walk(n_bars, drift, volatility, rng)

            # Open = previous close with some overnight gap
            opens = np.roll(close_prices, 1)
            opens[0] = close_prices[0] * rng.uniform(0.99, 1.01)

            # Generate OHLC
            highs = np.maximum(opens, close_prices) * (1 + rng.uniform(0, 0.01, n_bars))
            lows = np.minimum(opens, close_prices) * (1 - rng.uniform(0, 0.01, n_bars))

            # Volume lognormal
            volume = rng.lognormal(mean=10, sigma=1.5, size=n_bars).astype(int)
            volume = np.maximum(volume, 1)

            # VWAP approximation
            vwaps = (opens + highs + lows + close_prices) / 4

            for i in range(n_bars):
                all_rows.append({
                    "symbol": symbol,
                    "timestamp": timestamps[i].to_pydatetime(),
                    "open": float(opens[i]),
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "close": float(close_prices[i]),
                    "volume": int(volume[i]),
                    "frequency": frequency,
                    "vwap": float(vwaps[i]),
                })

        df = pd.DataFrame(all_rows)
        df = df.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
        return df

    def generate_scenarios(self) -> dict[str, pd.DataFrame]:
        """Generate a suite of named market scenarios for testing.

        Returns dict mapping scenario name to DataFrame.
        Each scenario covers ~500 bars at 1-minute frequency over ~1 trading day.
        """
        rng = np.random.default_rng(99)
        base_start = datetime(2024, 6, 10, 9, 30, tzinfo=timezone.utc)
        n_bars = 500
        timestamps = pd.date_range(start=base_start, periods=n_bars, freq="1min", tz="UTC")

        scenarios: dict[str, pd.DataFrame] = {}

        def _make_df(close_prices: np.ndarray, symbol_name: str) -> pd.DataFrame:
            opens = np.roll(close_prices, 1)
            opens[0] = close_prices[0] * rng.uniform(0.999, 1.001)
            highs = np.maximum(opens, close_prices) * (1 + rng.uniform(0, 0.005, n_bars))
            lows = np.minimum(opens, close_prices) * (1 - rng.uniform(0, 0.005, n_bars))
            volume = rng.lognormal(mean=9, sigma=1.2, size=n_bars).astype(int)
            volume = np.maximum(volume, 1)
            vwaps = (opens + highs + lows + close_prices) / 4

            rows = []
            for i in range(n_bars):
                rows.append({
                    "symbol": f"{symbol_name}",
                    "timestamp": timestamps[i].to_pydatetime(),
                    "open": float(opens[i]),
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "close": float(close_prices[i]),
                    "volume": int(volume[i]),
                    "frequency": BarFrequency.MINUTE_1,
                    "vwap": float(vwaps[i]),
                })
            return pd.DataFrame(rows)

        # Trend scenario: steady upward drift
        trend_price = 100 + np.cumsum(rng.normal(0.02, 0.05, n_bars))
        scenarios["trend"] = _make_df(np.maximum(trend_price, 1), "TREND")

        # Reversion scenario: oscillating around a mean
        reversion_price = 100 + rng.normal(0, 0.3, n_bars).cumsum()
        reversion_price = 100 + 3 * np.sin(np.linspace(0, 4 * np.pi, n_bars)) + rng.normal(0, 0.05, n_bars)
        scenarios["reversion"] = _make_df(np.maximum(reversion_price, 1), "REV")

        # Volatility spike: sudden burst of high variance
        vol_price = np.ones(n_bars) * 100
        vol_price[200:250] = 100 + rng.normal(0, 2.0, 50).cumsum()
        vol_price[400:] = 100 + np.cumsum(rng.normal(0.005, 0.03, n_bars - 400))
        scenarios["volatility_spike"] = _make_df(np.maximum(vol_price, 1), "VOL")

        # Gap scenario: overnight-style gaps
        gap_price = np.ones(n_bars) * 100
        for i in range(1, n_bars):
            gap_price[i] = gap_price[i - 1] + rng.normal(0, 0.05)
        gap_price[150] = gap_price[149] * 1.05  # gap up
        gap_price[300] = gap_price[299] * 0.93  # gap down
        gap_price[450] = gap_price[449] * 1.04  # gap up
        scenarios["gap"] = _make_df(np.maximum(gap_price, 1), "GAP")

        # Missing data: some rows have NaN prices
        missing_price = 100 + np.cumsum(rng.normal(0.01, 0.05, n_bars))
        missing_price[100:105] = np.nan  # missing chunk
        missing_price[250] = np.nan  # single missing
        df_missing = _make_df(np.maximum(np.nan_to_num(missing_price, nan=50), 1), "MISS")
        # Actually set some values to NaN
        df_missing.loc[100:104, ["open", "high", "low", "close", "vwap"]] = np.nan
        df_missing.loc[250, ["open", "high", "low", "close", "vwap"]] = np.nan
        scenarios["missing_data"] = df_missing

        # Flat period: price doesn't move
        flat_price = np.ones(n_bars) * 100
        flat_price[300:] = 100 + rng.normal(0, 0.01, n_bars - 300).cumsum()
        scenarios["flat"] = _make_df(np.maximum(flat_price, 1), "FLAT")

        # Regime change: trend → flat → reversion → spike
        rc_price = np.ones(n_bars) * 100
        rc_price[:125] = 100 + np.cumsum(rng.normal(0.02, 0.04, 125))  # uptrend
        rc_price[125:250] = rc_price[124] + rng.normal(0, 0.01, 125).cumsum()  # flat
        rc_price[250:375] = rc_price[249] - np.abs(rng.normal(0, 0.08, 125).cumsum()) + 1  # reversion
        rc_price[375:] = rc_price[374] + rng.normal(0, 0.10, n_bars - 375).cumsum()  # volatile
        scenarios["regime_change"] = _make_df(np.maximum(rc_price, 1), "REGIME")

        return scenarios

    @staticmethod
    def validate_bar(bar: Bar | dict) -> list[str]:
        """Validate a single Bar (or dict) and return list of issues (empty if valid)."""
        if isinstance(bar, dict):
            o, h, low, c = bar.get("open", 0), bar.get("high", 0), bar.get("low", 0), bar.get("close", 0)
            v = bar.get("volume", 0)
        else:
            o, h, low, c = bar.open, bar.high, bar.low, bar.close
            v = bar.volume

        issues: list[str] = []
        if o < 0 or h < 0 or low < 0 or c < 0:
            issues.append("Negative price in bar")
        if h < max(o, c):
            issues.append("High less than max(open, close)")
        if low > min(o, c):
            issues.append("Low greater than min(open, close)")
        if v < 0:
            issues.append("Negative volume")
        return issues

    @staticmethod
    def _freq_to_minutes(frequency: BarFrequency) -> int:
        mapping = {
            BarFrequency.MINUTE_1: 1,
            BarFrequency.MINUTE_5: 5,
            BarFrequency.MINUTE_15: 15,
            BarFrequency.MINUTE_30: 30,
            BarFrequency.HOUR_1: 60,
            BarFrequency.DAY_1: 1440,
        }
        return mapping.get(frequency, 1)

    @staticmethod
    def _random_walk(n: int, drift: float, volatility: float, rng: np.random.Generator) -> np.ndarray:
        """Generate a random walk price series starting from 100."""
        returns = rng.normal(drift, volatility, n)
        prices = 100 * np.exp(np.cumsum(returns))
        return np.maximum(prices, 0.01)
