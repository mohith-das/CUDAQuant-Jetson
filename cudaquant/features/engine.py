"""CPU feature engineering — reference implementations for validation.

All functions operate on numpy arrays. These serve as the ground-truth reference
against which GPU kernels are validated. NaN semantics: where a window is
incomplete (i < window-1), output is NaN.
"""

import numpy as np


def returns(prices: np.ndarray, log: bool = False) -> np.ndarray:
    """Compute period returns from price series.

    Args:
        prices: 1D array of prices.
        log: If True, compute log returns; else simple returns.

    Returns:
        1D array of same length. First element is NaN.
    """
    if len(prices) < 2:
        return np.full_like(prices, np.nan, dtype=np.float64)
    out = np.full_like(prices, np.nan, dtype=np.float64)
    if log:
        out[1:] = np.log(prices[1:] / prices[:-1])
    else:
        out[1:] = (prices[1:] - prices[:-1]) / prices[:-1]
    return out


def rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    """Rolling mean over window elements."""
    if window < 1:
        raise ValueError("window must be >= 1")
    out = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) >= window:
        # Use convolution for O(n) computation
        cumsum = np.cumsum(np.insert(arr.astype(np.float64), 0, 0))
        out[window - 1:] = (cumsum[window:] - cumsum[:-window]) / window
    return out


def rolling_variance(arr: np.ndarray, window: int, ddof: int = 0) -> np.ndarray:
    """Rolling variance over window elements."""
    if window < 2:
        return np.full_like(arr, np.nan, dtype=np.float64)
    out = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) >= window:
        mean = rolling_mean(arr, window)
        sq_mean = rolling_mean(arr * arr, window)
        out[window - 1:] = (sq_mean[window - 1:] - mean[window - 1:] ** 2)
        # Apply ddof correction
        if ddof > 0:
            out[window - 1:] *= window / (window - ddof)
        out[out < 0] = 0.0  # clamp numerical noise
    return out


def rolling_std(arr: np.ndarray, window: int, ddof: int = 0) -> np.ndarray:
    """Rolling standard deviation over window elements."""
    return np.sqrt(rolling_variance(arr, window, ddof))


def rolling_min(arr: np.ndarray, window: int) -> np.ndarray:
    """Rolling minimum over window elements."""
    if window < 1:
        raise ValueError("window must be >= 1")
    out = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) >= window:
        for i in range(window - 1, len(arr)):
            out[i] = np.min(arr[i - window + 1 : i + 1])
    return out


def rolling_max(arr: np.ndarray, window: int) -> np.ndarray:
    """Rolling maximum over window elements."""
    if window < 1:
        raise ValueError("window must be >= 1")
    out = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) >= window:
        for i in range(window - 1, len(arr)):
            out[i] = np.max(arr[i - window + 1 : i + 1])
    return out


def rolling_sum(arr: np.ndarray, window: int) -> np.ndarray:
    """Rolling sum over window elements."""
    if window < 1:
        raise ValueError("window must be >= 1")
    out = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) >= window:
        cumsum = np.cumsum(np.insert(arr.astype(np.float64), 0, 0))
        out[window - 1:] = cumsum[window:] - cumsum[:-window]
    return out


def rolling_zscore(arr: np.ndarray, window: int) -> np.ndarray:
    """Rolling z-score: (value - rolling_mean) / rolling_std."""
    mean = rolling_mean(arr, window)
    std = rolling_std(arr, window)
    out = np.full_like(arr, np.nan, dtype=np.float64)
    mask = std > 1e-10
    out[mask] = (arr[mask] - mean[mask]) / std[mask]
    return out


def rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index (Wilder's smoothing)."""
    if len(prices) < period + 1:
        return np.full_like(prices, np.nan, dtype=np.float64)
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    out = np.full_like(prices, np.nan, dtype=np.float64)
    # First average is simple mean
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    out[period] = 100.0 - 100.0 / (1.0 + (avg_gain / avg_loss)) if avg_loss > 0 else 100.0

    # Wilder's smoothing
    for i in range(period + 1, len(prices)):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        out[i] = 100.0 - 100.0 / (1.0 + (avg_gain / avg_loss)) if avg_loss > 0 else 100.0

    return out


def atr(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
) -> np.ndarray:
    """Average True Range."""
    n = len(close)
    if n < 2:
        return np.full(n, np.nan, dtype=np.float64)

    tr = np.zeros(n, dtype=np.float64)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    # Wilder's smoothing
    out = np.full(n, np.nan, dtype=np.float64)
    if n > period:
        out[period] = np.mean(tr[1 : period + 1])
        for i in range(period + 1, n):
            out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def vwap(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray,
) -> np.ndarray:
    """Volume-Weighted Average Price (cumulative from start)."""
    typical = (high + low + close) / 3.0
    cum_vp = np.cumsum(typical * volume)
    cum_vol = np.cumsum(volume.astype(np.float64))
    out = np.full_like(close, np.nan, dtype=np.float64)
    mask = cum_vol > 0
    out[mask] = cum_vp[mask] / cum_vol[mask]
    return out


def vwap_deviation(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray,
) -> np.ndarray:
    """Deviation of close from cumulative VWAP, as a fraction."""
    v = vwap(high, low, close, volume)
    out = np.full_like(close, np.nan, dtype=np.float64)
    mask = ~np.isnan(v)
    out[mask] = (close[mask] - v[mask]) / v[mask]
    return out


def realized_volatility(returns_series: np.ndarray, window: int, annualize: int = 252) -> np.ndarray:
    """Realized volatility: rolling std of returns, annualized."""
    return rolling_std(returns_series, window) * np.sqrt(annualize)


def relative_volume(volume: np.ndarray, window: int = 20) -> np.ndarray:
    """Volume relative to its rolling average."""
    mean_vol = rolling_mean(volume.astype(np.float64), window)
    out = np.full_like(volume, np.nan, dtype=np.float64)
    mask = mean_vol > 0
    out[mask] = volume[mask].astype(np.float64) / mean_vol[mask]
    return out


def volume_zscore(volume: np.ndarray, window: int = 20) -> np.ndarray:
    """Z-score of volume relative to rolling mean/std."""
    return rolling_zscore(volume.astype(np.float64), window)


def momentum(prices: np.ndarray, period: int = 20) -> np.ndarray:
    """Price momentum: (price[t] / price[t-period]) - 1."""
    out = np.full_like(prices, np.nan, dtype=np.float64)
    if len(prices) > period:
        out[period:] = prices[period:] / prices[:-period] - 1.0
    return out


def rolling_beta(
    returns_a: np.ndarray, returns_b: np.ndarray, window: int = 60,
) -> np.ndarray:
    """Rolling beta of returns_a against returns_b (market) using OLS slope."""
    n = len(returns_a)
    out = np.full(n, np.nan, dtype=np.float64)
    if n < window:
        return out
    for i in range(window - 1, n):
        x = returns_b[i - window + 1 : i + 1]
        y = returns_a[i - window + 1 : i + 1]
        valid = ~(np.isnan(x) | np.isnan(y))
        if valid.sum() < window // 2:
            continue
        xv, yv = x[valid], y[valid]
        cov = np.cov(xv, yv, ddof=0)[0, 1]
        var_x = np.var(xv, ddof=0)
        if var_x > 1e-12:
            out[i] = cov / var_x
    return out


def rolling_correlation(
    returns_a: np.ndarray, returns_b: np.ndarray, window: int = 60,
) -> np.ndarray:
    """Rolling Pearson correlation between two return series."""
    n = len(returns_a)
    out = np.full(n, np.nan, dtype=np.float64)
    if n < window:
        return out
    for i in range(window - 1, n):
        x = returns_a[i - window + 1 : i + 1]
        y = returns_b[i - window + 1 : i + 1]
        valid = ~(np.isnan(x) | np.isnan(y))
        if valid.sum() < window // 2:
            continue
        corr = np.corrcoef(x[valid], y[valid])[0, 1]
        out[i] = corr
    return out


def market_relative_return(returns: np.ndarray, market_returns: np.ndarray) -> np.ndarray:
    """Excess return over market."""
    out = np.full_like(returns, np.nan, dtype=np.float64)
    mask = ~(np.isnan(returns) | np.isnan(market_returns))
    out[mask] = returns[mask] - market_returns[mask]
    return out


def overnight_gap(close: np.ndarray, opens: np.ndarray) -> np.ndarray:
    """Overnight gap: (open[t] / close[t-1]) - 1."""
    out = np.full_like(close, np.nan, dtype=np.float64)
    if len(close) > 1:
        out[1:] = opens[1:] / close[:-1] - 1.0
    return out


def distance_from_high(prices: np.ndarray, window: int = 20) -> np.ndarray:
    """Distance of current price from rolling high, as a fraction."""
    high = rolling_max(prices, window)
    out = np.full_like(prices, np.nan, dtype=np.float64)
    mask = ~np.isnan(high)
    out[mask] = (prices[mask] - high[mask]) / high[mask]
    return out


def distance_from_low(prices: np.ndarray, window: int = 20) -> np.ndarray:
    """Distance of current price from rolling low, as a fraction."""
    low = rolling_min(prices, window)
    out = np.full_like(prices, np.nan, dtype=np.float64)
    mask = ~np.isnan(low)
    out[mask] = (prices[mask] - low[mask]) / low[mask]
    return out


def time_of_day_encoding(n_bars: int, bars_per_day: int = 390) -> np.ndarray:
    """Cyclical time-of-day encoding: sin/cos of bar position within day."""
    positions = np.arange(n_bars) % bars_per_day
    angle = 2 * np.pi * positions / bars_per_day
    return np.column_stack([np.sin(angle), np.cos(angle)])
