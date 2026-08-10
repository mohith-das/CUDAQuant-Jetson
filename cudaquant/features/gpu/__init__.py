"""GPU-accelerated feature kernels and bindings."""

from cudaquant.features.gpu.kernels import (
    gpu_log_returns,
    gpu_rolling_max,
    gpu_rolling_mean,
    gpu_rolling_min,
    gpu_rolling_std,
    gpu_rolling_sum,
    gpu_rolling_variance,
    gpu_rolling_zscore,
    gpu_simple_returns,
)

__all__ = [
    "gpu_log_returns",
    "gpu_rolling_max",
    "gpu_rolling_mean",
    "gpu_rolling_min",
    "gpu_rolling_std",
    "gpu_rolling_sum",
    "gpu_rolling_variance",
    "gpu_rolling_zscore",
    "gpu_simple_returns",
]
