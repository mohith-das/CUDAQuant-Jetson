"""GPU-accelerated feature kernels — high-level Python API.

Each function accepts numpy arrays, runs on GPU if available, or gracefully
falls back to CPU NumPy implementation. Functions raise no CUDA errors — if
GPU is unavailable, the CPU path is used transparently.
"""

import ctypes
import logging

import numpy as np

from cudaquant.features.engine import (
    returns as _cpu_returns,
)
from cudaquant.features.engine import (
    rolling_max as _cpu_rolling_max,
)
from cudaquant.features.engine import (
    rolling_mean as _cpu_rolling_mean,
)
from cudaquant.features.engine import (
    rolling_min as _cpu_rolling_min,
)
from cudaquant.features.engine import (
    rolling_std as _cpu_rolling_std,
)
from cudaquant.features.engine import (
    rolling_sum as _cpu_rolling_sum,
)
from cudaquant.features.engine import (
    rolling_variance as _cpu_rolling_variance,
)
from cudaquant.features.engine import (
    rolling_zscore as _cpu_rolling_zscore,
)
from cudaquant.features.gpu.bindings import _allocate_and_copy, _copy_back_and_free, _load_library

logger = logging.getLogger(__name__)


def _gpu_fallback(cpu_fn, *args, **kwargs):
    """Run CPU fallback and log a debug message."""
    logger.debug("GPU unavailable, using CPU fallback for %s", cpu_fn.__name__)
    return cpu_fn(*args, **kwargs)


def _cast_to_float_ptr(d_ptr):
    """Cast a c_void_p to POINTER(c_float) for kernel calls."""
    return ctypes.cast(d_ptr, ctypes.POINTER(ctypes.c_float))


# ── Rolling mean ─────────────────────────────────────────────────────────────


def gpu_rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    """GPU-accelerated rolling mean. Falls back to CPU if GPU unavailable."""
    lib = _load_library()
    if lib is None or len(arr) < 1:
        return _gpu_fallback(_cpu_rolling_mean, arr, window)

    d_in, n = _allocate_and_copy(arr)
    d_out, _ = _allocate_and_copy(np.zeros(n, dtype=np.float32))
    lib.launch_rolling_mean(_cast_to_float_ptr(d_in), _cast_to_float_ptr(d_out), n, window)
    result = _copy_back_and_free(d_out, n)
    ctypes.cdll.LoadLibrary("libcudart.so").cudaFree(d_in)
    return result.astype(np.float64)


def gpu_rolling_std(arr: np.ndarray, window: int) -> np.ndarray:
    """GPU-accelerated rolling standard deviation."""
    lib = _load_library()
    if lib is None or len(arr) < 1:
        return _gpu_fallback(_cpu_rolling_std, arr, window)

    d_in, n = _allocate_and_copy(arr)
    d_out, _ = _allocate_and_copy(np.zeros(n, dtype=np.float32))
    lib.launch_rolling_std(_cast_to_float_ptr(d_in), _cast_to_float_ptr(d_out), n, window)
    result = _copy_back_and_free(d_out, n)
    ctypes.cdll.LoadLibrary("libcudart.so").cudaFree(d_in)
    return result.astype(np.float64)


def gpu_rolling_variance(arr: np.ndarray, window: int) -> np.ndarray:
    """GPU-accelerated rolling variance."""
    lib = _load_library()
    if lib is None or len(arr) < 1:
        return _gpu_fallback(_cpu_rolling_variance, arr, window)

    d_in, n = _allocate_and_copy(arr)
    d_out, _ = _allocate_and_copy(np.zeros(n, dtype=np.float32))
    lib.launch_rolling_variance(_cast_to_float_ptr(d_in), _cast_to_float_ptr(d_out), n, window)
    result = _copy_back_and_free(d_out, n)
    ctypes.cdll.LoadLibrary("libcudart.so").cudaFree(d_in)
    return result.astype(np.float64)


def gpu_rolling_min(arr: np.ndarray, window: int) -> np.ndarray:
    """GPU-accelerated rolling minimum."""
    lib = _load_library()
    if lib is None or len(arr) < 1:
        return _gpu_fallback(_cpu_rolling_min, arr, window)

    d_in, n = _allocate_and_copy(arr)
    d_out, _ = _allocate_and_copy(np.zeros(n, dtype=np.float32))
    lib.launch_rolling_min(_cast_to_float_ptr(d_in), _cast_to_float_ptr(d_out), n, window)
    result = _copy_back_and_free(d_out, n)
    ctypes.cdll.LoadLibrary("libcudart.so").cudaFree(d_in)
    return result.astype(np.float64)


def gpu_rolling_max(arr: np.ndarray, window: int) -> np.ndarray:
    """GPU-accelerated rolling maximum."""
    lib = _load_library()
    if lib is None or len(arr) < 1:
        return _gpu_fallback(_cpu_rolling_max, arr, window)

    d_in, n = _allocate_and_copy(arr)
    d_out, _ = _allocate_and_copy(np.zeros(n, dtype=np.float32))
    lib.launch_rolling_max(_cast_to_float_ptr(d_in), _cast_to_float_ptr(d_out), n, window)
    result = _copy_back_and_free(d_out, n)
    ctypes.cdll.LoadLibrary("libcudart.so").cudaFree(d_in)
    return result.astype(np.float64)


def gpu_rolling_sum(arr: np.ndarray, window: int) -> np.ndarray:
    """GPU-accelerated rolling sum."""
    lib = _load_library()
    if lib is None or len(arr) < 1:
        return _gpu_fallback(_cpu_rolling_sum, arr, window)

    d_in, n = _allocate_and_copy(arr)
    d_out, _ = _allocate_and_copy(np.zeros(n, dtype=np.float32))
    lib.launch_rolling_sum(_cast_to_float_ptr(d_in), _cast_to_float_ptr(d_out), n, window)
    result = _copy_back_and_free(d_out, n)
    ctypes.cdll.LoadLibrary("libcudart.so").cudaFree(d_in)
    return result.astype(np.float64)


def gpu_rolling_zscore(arr: np.ndarray, window: int) -> np.ndarray:
    """GPU-accelerated rolling z-score."""
    lib = _load_library()
    if lib is None or len(arr) < 1:
        return _gpu_fallback(_cpu_rolling_zscore, arr, window)

    d_in, n = _allocate_and_copy(arr)
    d_out, _ = _allocate_and_copy(np.zeros(n, dtype=np.float32))
    lib.launch_rolling_zscore(_cast_to_float_ptr(d_in), _cast_to_float_ptr(d_out), n, window)
    result = _copy_back_and_free(d_out, n)
    ctypes.cdll.LoadLibrary("libcudart.so").cudaFree(d_in)
    return result.astype(np.float64)


def gpu_simple_returns(prices: np.ndarray) -> np.ndarray:
    """GPU-accelerated simple returns."""
    lib = _load_library()
    if lib is None or len(prices) < 2:
        return _cpu_returns(prices, log=False)

    d_in, n = _allocate_and_copy(prices)
    d_out, _ = _allocate_and_copy(np.zeros(n, dtype=np.float32))
    lib.launch_simple_returns(_cast_to_float_ptr(d_in), _cast_to_float_ptr(d_out), n)
    result = _copy_back_and_free(d_out, n)
    ctypes.cdll.LoadLibrary("libcudart.so").cudaFree(d_in)
    return result.astype(np.float64)


def gpu_log_returns(prices: np.ndarray) -> np.ndarray:
    """GPU-accelerated log returns."""
    lib = _load_library()
    if lib is None or len(prices) < 2:
        return _cpu_returns(prices, log=True)

    d_in, n = _allocate_and_copy(prices)
    d_out, _ = _allocate_and_copy(np.zeros(n, dtype=np.float32))
    lib.launch_log_returns(_cast_to_float_ptr(d_in), _cast_to_float_ptr(d_out), n)
    result = _copy_back_and_free(d_out, n)
    ctypes.cdll.LoadLibrary("libcudart.so").cudaFree(d_in)
    return result.astype(np.float64)
