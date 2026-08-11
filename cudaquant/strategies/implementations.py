"""Baseline trading strategies for CUDAQuant.

Each strategy implements the Strategy ABC and records parameters, entry/exit logic,
risk assumptions, and experiment origin. All strategies MUST NOT look ahead in data.
"""

import numpy as np
import pandas as pd

from cudaquant.features import rolling_max, rolling_min, rolling_zscore
from cudaquant.strategies.base import Strategy


class IntradayMomentum(Strategy):
    """Buy when price breaks above N-period high; sell when below N-period low.

    Parameters:
        lookback (int): Lookback window for high/low computation.
        exit_lookback (int): Lookback window for exit signal (defaults to lookback).
    """

    def __init__(self, lookback: int = 20, exit_lookback: int | None = None):
        super().__init__(
            name="intraday_momentum",
            parameters={"lookback": lookback, "exit_lookback": exit_lookback or lookback},
        )
        self.lookback = lookback
        self.exit_lookback = exit_lookback or lookback
        self._cached_high: np.ndarray | None = None
        self._cached_low: np.ndarray | None = None
        self._cached_len: int = 0

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate position signals: 1 (long), -1 (short), 0 (flat).

        Entry: close > rolling_high[lookback] → long
               close < rolling_low[lookback] → short
        Exit:  close < rolling_low[exit_lookback] → flat (from long)
               close > rolling_high[exit_lookback] → flat (from short)

        Caches rolling feature computation — only recomputes when data grows.
        """
        close = data["close"].values.astype(np.float64)
        n = len(close)

        # Cache: only recompute when data has grown
        if self._cached_high is None or n != self._cached_len:
            self._cached_high = rolling_max(close, self.lookback)
            self._cached_low = rolling_min(close, self.lookback)
            self._cached_len = n
        entry_high = self._cached_high
        entry_low = self._cached_low
        exit_high = rolling_max(close, self.exit_lookback)
        exit_low = rolling_min(close, self.exit_lookback)

        signals = np.zeros(n, dtype=int)
        position = 0

        for i in range(max(self.lookback, self.exit_lookback), n):
            if np.isnan(close[i]):
                continue

            if position == 0:
                if close[i] > entry_high[i - 1]:
                    position = 1
                elif close[i] < entry_low[i - 1]:
                    position = -1
            elif position == 1:
                if close[i] < exit_low[i - 1]:
                    position = 0
            elif position == -1 and close[i] > exit_high[i - 1]:
                position = 0

            signals[i] = position

        return pd.Series(signals, index=data.index)


class MeanReversion(Strategy):
    """Buy when z-score < -entry_threshold; sell when > +exit_threshold.

    Parameters:
        window (int): Rolling window for z-score computation.
        entry_threshold (float): Z-score threshold to enter long.
        exit_threshold (float): Z-score threshold to exit.
        mean_reversion_window (int): Window for mean computation.
    """

    def __init__(
        self,
        window: int = 20,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
    ):
        super().__init__(
            name="mean_reversion",
            parameters={
                "window": window,
                "entry_threshold": entry_threshold,
                "exit_threshold": exit_threshold,
            },
        )
        self.window = window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self._cached_zscore: np.ndarray | None = None
        self._cached_len: int = 0

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on rolling z-score.

        Caches z-score computation — only recomputes when data grows,
        not on every bar of the walk-forward loop (~30x speedup).
        """
        close = data["close"].values.astype(np.float64)
        n = len(close)

        # Cache: only recompute z-score when data has grown
        if self._cached_zscore is None or n != self._cached_len:
            self._cached_zscore = rolling_zscore(close, self.window)
            self._cached_len = n
        zscore = self._cached_zscore

        signals = np.zeros(n, dtype=int)
        position = 0

        for i in range(self.window, n):
            if np.isnan(zscore[i]):
                continue

            if position == 0:
                if zscore[i] < -self.entry_threshold:
                    position = 1  # oversold → long
                elif zscore[i] > self.entry_threshold:
                    position = -1  # overbought → short
            elif position == 1:
                if zscore[i] > -self.exit_threshold:
                    position = 0  # reverted
            elif position == -1 and zscore[i] < self.exit_threshold:
                position = 0  # reverted

            signals[i] = position

        return pd.Series(signals, index=data.index)


class PairsRelativeValue(Strategy):
    """Spread trading: long the underperformer, short the outperformer.

    Trades the z-score of the log price ratio between two assets.
    Assumes data contains both symbols with a 'symbol' column.

    Parameters:
        symbol_a (str): First symbol in the pair.
        symbol_b (str): Second symbol in the pair.
        window (int): Rolling window for mean/std of spread.
        entry_threshold (float): Z-score threshold to enter.
        exit_threshold (float): Z-score threshold to exit.
    """

    def __init__(
        self,
        symbol_a: str,
        symbol_b: str,
        window: int = 60,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
    ):
        super().__init__(
            name=f"pairs_{symbol_a}_{symbol_b}",
            parameters={
                "symbol_a": symbol_a,
                "symbol_b": symbol_b,
                "window": window,
                "entry_threshold": entry_threshold,
                "exit_threshold": exit_threshold,
            },
        )
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b
        self.window = window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals for symbol_a only (hedge with symbol_b).

        Spread = log(price_a / price_b). Trade when spread z-score exceeds threshold.
        Long A (short B) when spread is cheap (z < -entry).
        Short A (long B) when spread is rich (z > +entry).
        """
        df_a = data[data["symbol"] == self.symbol_a].sort_values("timestamp")
        df_b = data[data["symbol"] == self.symbol_b].sort_values("timestamp")

        if len(df_a) == 0 or len(df_b) == 0:
            return pd.Series(np.zeros(len(data)), index=data.index)

        # Align timestamps
        merged = pd.merge(
            df_a[["timestamp", "close"]],
            df_b[["timestamp", "close"]],
            on="timestamp",
            suffixes=("_a", "_b"),
            how="inner",
        )

        if len(merged) < self.window:
            return pd.Series(np.zeros(len(data)), index=data.index)

        spread = np.log(merged["close_a"].values / merged["close_b"].values)
        zscore = rolling_zscore(spread, self.window)

        signals = np.zeros(len(data), dtype=int)
        position = 0

        for i in range(len(merged)):
            ts = merged.iloc[i]["timestamp"]
            idx = data[data["timestamp"] == ts].index
            if len(idx) == 0:
                continue
            data_idx = idx[0]

            if i < self.window or np.isnan(zscore[i]):
                continue

            if position == 0:
                if zscore[i] < -self.entry_threshold:
                    position = 1  # A cheap relative to B → long A
                elif zscore[i] > self.entry_threshold:
                    position = -1  # A rich relative to B → short A
            elif position == 1:
                if zscore[i] > -self.exit_threshold:
                    position = 0
            elif position == -1 and zscore[i] < self.exit_threshold:
                position = 0

            signals[data_idx] = position

        return pd.Series(signals, index=data.index)
