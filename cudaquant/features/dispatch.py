"""Feature dispatch layer — routes to GPU or CPU based on config, library
availability, and empirically-measured size thresholds.

Each function mirrors the cudaquant.features.engine API but automatically
selects the fastest backend. All decisions are transparent and auditable
via get_stats().
"""

import logging
import threading

import numpy as np

from cudaquant.config.settings import settings
from cudaquant.features import engine as _cpu
from cudaquant.features.gpu import bindings as _gpu_bindings
from cudaquant.features.gpu import kernels as _gpu_kernels

logger = logging.getLogger(__name__)

# ── Empirically-measured size thresholds (Jetson Orin, CUDA 13.2) ────────────
# Below this array length, CPU is faster (GPU launch + transfer overhead
# dominates). Above, GPU wins. "inf" means CPU always wins at measured sizes.
# Measured 2026-08-09 with benchmarks/measure_crossover.py.

_THRESHOLDS: dict[str, int | float] = {
    "rolling_mean": float("inf"),       # CPU always wins (tied at 100k)
    "rolling_std": 100_000,             # GPU wins at 100k+
    "rolling_variance": 100_000,        # GPU wins at 100k+
    "rolling_min": 1_000,               # GPU wins at 1k+ (CPU is O(n^2)-ish)
    "rolling_max": 1_000,               # GPU wins at 1k+ (CPU is O(n^2)-ish)
    "rolling_sum": float("inf"),        # CPU always wins
    "rolling_zscore": 20_000,           # GPU wins at 20k+
    "returns": float("inf"),            # CPU always wins
    "log_returns": float("inf"),        # CPU always wins
}

# ── Call tracking (thread-safe) ──────────────────────────────────────────────

_stats_lock = threading.Lock()
_stats: dict[str, int] = {
    "gpu_calls": {},
    "cpu_calls": {},
    "gpu_bypass_config": 0,   # config CUDA_ENABLED=False
    "gpu_bypass_no_lib": 0,   # library not loadable
    "gpu_bypass_size": 0,     # below threshold
}


def _record(backend: str, fn_name: str) -> None:
    """Record a call for observability."""
    with _stats_lock:
        if backend == "gpu":
            _stats["gpu_calls"][fn_name] = _stats["gpu_calls"].get(fn_name, 0) + 1
        else:
            _stats["cpu_calls"][fn_name] = _stats["cpu_calls"].get(fn_name, 0) + 1


def get_stats() -> dict:
    """Return current dispatch statistics. Thread-safe snapshot."""
    with _stats_lock:
        return {
            "gpu_calls": dict(_stats["gpu_calls"]),
            "cpu_calls": dict(_stats["cpu_calls"]),
            "gpu_bypass_config": _stats["gpu_bypass_config"],
            "gpu_bypass_no_lib": _stats["gpu_bypass_no_lib"],
            "gpu_bypass_size": _stats["gpu_bypass_size"],
        }


def reset_stats() -> None:
    """Reset dispatch statistics (for testing)."""
    with _stats_lock:
        _stats["gpu_calls"].clear()
        _stats["cpu_calls"].clear()
        _stats["gpu_bypass_config"] = 0
        _stats["gpu_bypass_no_lib"] = 0
        _stats["gpu_bypass_size"] = 0


def _should_use_gpu(fn_name: str, n_elements: int) -> tuple[bool, str]:
    """Determine whether to use GPU for a given function and array size.

    Returns (use_gpu, reason).
    """
    if not settings.CUDA_ENABLED:
        with _stats_lock:
            _stats["gpu_bypass_config"] += 1
        return False, "config_disabled"

    if _gpu_bindings._load_library() is None:
        with _stats_lock:
            _stats["gpu_bypass_no_lib"] += 1
        return False, "library_not_found"

    threshold = _THRESHOLDS.get(fn_name, float("inf"))
    if n_elements < threshold:
        with _stats_lock:
            _stats["gpu_bypass_size"] += 1
        return False, "below_threshold"

    return True, "ok"


# ── Dispatched feature functions ─────────────────────────────────────────────


def rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    use_gpu, reason = _should_use_gpu("rolling_mean", len(arr))
    if use_gpu:
        result = _gpu_kernels.gpu_rolling_mean(arr, window)
        _record("gpu", "rolling_mean")
        return result
    _record("cpu", "rolling_mean")
    return _cpu.rolling_mean(arr, window)


def rolling_std(arr: np.ndarray, window: int, ddof: int = 0) -> np.ndarray:
    use_gpu, reason = _should_use_gpu("rolling_std", len(arr))
    if use_gpu:
        result = _gpu_kernels.gpu_rolling_std(arr, window)
        _record("gpu", "rolling_std")
        return result
    _record("cpu", "rolling_std")
    return _cpu.rolling_std(arr, window, ddof)


def rolling_variance(arr: np.ndarray, window: int, ddof: int = 0) -> np.ndarray:
    use_gpu, reason = _should_use_gpu("rolling_variance", len(arr))
    if use_gpu:
        result = _gpu_kernels.gpu_rolling_variance(arr, window)
        _record("gpu", "rolling_variance")
        return result
    _record("cpu", "rolling_variance")
    return _cpu.rolling_variance(arr, window, ddof)


def rolling_min(arr: np.ndarray, window: int) -> np.ndarray:
    use_gpu, reason = _should_use_gpu("rolling_min", len(arr))
    if use_gpu:
        result = _gpu_kernels.gpu_rolling_min(arr, window)
        _record("gpu", "rolling_min")
        return result
    _record("cpu", "rolling_min")
    return _cpu.rolling_min(arr, window)


def rolling_max(arr: np.ndarray, window: int) -> np.ndarray:
    use_gpu, reason = _should_use_gpu("rolling_max", len(arr))
    if use_gpu:
        result = _gpu_kernels.gpu_rolling_max(arr, window)
        _record("gpu", "rolling_max")
        return result
    _record("cpu", "rolling_max")
    return _cpu.rolling_max(arr, window)


def rolling_sum(arr: np.ndarray, window: int) -> np.ndarray:
    use_gpu, reason = _should_use_gpu("rolling_sum", len(arr))
    if use_gpu:
        result = _gpu_kernels.gpu_rolling_sum(arr, window)
        _record("gpu", "rolling_sum")
        return result
    _record("cpu", "rolling_sum")
    return _cpu.rolling_sum(arr, window)


def rolling_zscore(arr: np.ndarray, window: int) -> np.ndarray:
    use_gpu, reason = _should_use_gpu("rolling_zscore", len(arr))
    if use_gpu:
        result = _gpu_kernels.gpu_rolling_zscore(arr, window)
        _record("gpu", "rolling_zscore")
        return result
    _record("cpu", "rolling_zscore")
    return _cpu.rolling_zscore(arr, window)


def returns(arr: np.ndarray, log: bool = False) -> np.ndarray:
    use_gpu, reason = _should_use_gpu("returns" if not log else "log_returns", len(arr))
    if use_gpu:
        result = _gpu_kernels.gpu_simple_returns(arr) if not log else _gpu_kernels.gpu_log_returns(arr)
        _record("gpu", "returns")
        return result
    _record("cpu", "returns")
    return _cpu.returns(arr, log=log)


# ── Non-dispatchable features (CPU-only, no GPU kernel exists) ───────────────
# These are imported directly from engine — no GPU kernel exists for them yet.

from cudaquant.features.engine import (  # noqa: E402, F401
    atr,
    distance_from_high,
    distance_from_low,
    market_relative_return,
    momentum,
    overnight_gap,
    realized_volatility,
    relative_volume,
    rolling_beta,
    rolling_correlation,
    rsi,
    time_of_day_encoding,
    volume_zscore,
    vwap,
    vwap_deviation,
)
