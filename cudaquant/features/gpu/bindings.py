"""ctypes bindings for CUDAQuant GPU kernels.

Loads the compiled CUDA shared library and provides Python-callable wrappers.
Gracefully falls back to CPU if the library is unavailable.
"""

import ctypes
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ── Library discovery ────────────────────────────────────────────────────────


def _find_library() -> str | None:
    """Find the compiled CUDA kernel library."""
    search_paths = [
        # Project lib directory
        Path(__file__).resolve().parent.parent.parent.parent / "cuda" / "lib",
        Path(__file__).resolve().parent.parent.parent.parent / "cuda" / "build",
        # System paths
        Path("/usr/local/lib"),
        Path("/usr/lib"),
    ]

    lib_names = ["libcudaquant_kernels.so", "libcudaquant_kernels.dylib"]

    for search in search_paths:
        for name in lib_names:
            candidate = search / name
            if candidate.exists():
                return str(candidate)

    return None


_lib_path = _find_library()
_lib: Any = None
_gpu_available = False


def _load_library() -> Any:
    """Load the CUDA kernel library. Returns None if unavailable."""
    global _lib, _gpu_available, _lib_path

    if _lib is not None:
        return _lib

    _lib_path = _find_library()

    if _lib_path is None:
        logger.debug("CUDA kernel library not found — GPU features will use CPU fallback")
        return None

    try:
        _lib = ctypes.cdll.LoadLibrary(_lib_path)

        # ── Rolling statistics ────────────────────────────────────────────
        _lib.launch_rolling_mean.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.c_int, ctypes.c_int,
        ]
        _lib.launch_rolling_sum.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.c_int, ctypes.c_int,
        ]
        _lib.launch_rolling_variance.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.c_int, ctypes.c_int,
        ]
        _lib.launch_rolling_std.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.c_int, ctypes.c_int,
        ]
        _lib.launch_rolling_min.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.c_int, ctypes.c_int,
        ]
        _lib.launch_rolling_max.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.c_int, ctypes.c_int,
        ]

        # ── Returns ───────────────────────────────────────────────────────
        _lib.launch_simple_returns.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.c_int,
        ]
        _lib.launch_log_returns.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.c_int,
        ]

        # ── Z-score ───────────────────────────────────────────────────────
        _lib.launch_rolling_zscore.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.c_int, ctypes.c_int,
        ]

        _gpu_available = True
        logger.info(f"CUDA kernel library loaded: {_lib_path}")
        return _lib

    except OSError as e:
        logger.debug(f"Failed to load CUDA library: {e}")
        return None


def gpu_available() -> bool:
    """Check if GPU kernels are available."""
    if _lib is None:
        _load_library()
    return _gpu_available


# ── GPU memory helpers ───────────────────────────────────────────────────────


def _allocate_and_copy(arr: np.ndarray):
    """Allocate GPU memory and copy numpy array. Returns (d_ptr, n)."""
    lib = _load_library()
    if lib is None:
        return None, len(arr)

    n = len(arr)
    arr_f32 = arr.astype(np.float32, copy=False)
    d_ptr = ctypes.c_void_p()
    ctypes.cdll.LoadLibrary("libcudart.so").cudaMalloc(
        ctypes.byref(d_ptr), n * ctypes.sizeof(ctypes.c_float)
    )
    ctypes.cdll.LoadLibrary("libcudart.so").cudaMemcpy(
        d_ptr, arr_f32.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        n * ctypes.sizeof(ctypes.c_float), 1  # cudaMemcpyHostToDevice = 1
    )
    return d_ptr, n


def _copy_back_and_free(d_ptr, n: int) -> np.ndarray:
    """Copy result back from GPU, free memory, return numpy array."""
    cudart = ctypes.cdll.LoadLibrary("libcudart.so")
    out = np.empty(n, dtype=np.float32)
    cudart.cudaMemcpy(
        out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        d_ptr, n * ctypes.sizeof(ctypes.c_float), 2  # cudaMemcpyDeviceToHost = 2
    )
    cudart.cudaFree(d_ptr)
    return out
