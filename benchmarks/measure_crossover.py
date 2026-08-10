#!/usr/bin/env python3
"""Measure CPU vs GPU crossover points on Jetson."""
import time

import numpy as np

from cudaquant.features.engine import (
    returns as cpu_ret,
)
from cudaquant.features.engine import (
    rolling_max as cpu_max,
)
from cudaquant.features.engine import (
    rolling_mean as cpu_m,
)
from cudaquant.features.engine import (
    rolling_min as cpu_min,
)
from cudaquant.features.engine import (
    rolling_std as cpu_s,
)
from cudaquant.features.engine import (
    rolling_sum as cpu_sum,
)
from cudaquant.features.engine import (
    rolling_variance as cpu_v,
)
from cudaquant.features.engine import (
    rolling_zscore as cpu_z,
)
from cudaquant.features.gpu.kernels import (
    gpu_rolling_max as gpu_max,
)
from cudaquant.features.gpu.kernels import (
    gpu_rolling_mean as gpu_m,
)
from cudaquant.features.gpu.kernels import (
    gpu_rolling_min as gpu_min,
)
from cudaquant.features.gpu.kernels import (
    gpu_rolling_std as gpu_s,
)
from cudaquant.features.gpu.kernels import (
    gpu_rolling_sum as gpu_sum,
)
from cudaquant.features.gpu.kernels import (
    gpu_rolling_variance as gpu_v,
)
from cudaquant.features.gpu.kernels import (
    gpu_rolling_zscore as gpu_z,
)
from cudaquant.features.gpu.kernels import (
    gpu_simple_returns as gpu_ret,
)

window = 20
n_runs = 5
sizes = [220, 1000, 5000, 20000, 100000]

print(f"{'fn':>20s} {'n':>7s} {'CPU_ms':>10s} {'GPU_ms':>10s} {'winner':>6s}")
print("-" * 58)

for n in sizes:
    arr = np.cumsum(np.random.randn(n).astype(np.float32)) + 100.0
    arr64 = arr.astype(np.float64)
    for name, cpu_fn, gpu_fn in [
        ("rolling_mean", cpu_m, gpu_m),
        ("rolling_std", cpu_s, gpu_s),
        ("rolling_zscore", cpu_z, gpu_z),
        ("rolling_min", cpu_min, gpu_min),
        ("rolling_max", cpu_max, gpu_max),
        ("rolling_sum", cpu_sum, gpu_sum),
        ("rolling_variance", cpu_v, gpu_v),
        ("returns", cpu_ret, gpu_ret),
    ]:
        if name == "returns":
            t0 = time.perf_counter()
            for _ in range(n_runs):
                cpu_fn(arr64, False)
            ct = (time.perf_counter() - t0) / n_runs * 1000
            t0 = time.perf_counter()
            for _ in range(n_runs):
                gpu_fn(arr)
            gt = (time.perf_counter() - t0) / n_runs * 1000
        else:
            t0 = time.perf_counter()
            for _ in range(n_runs):
                cpu_fn(arr64, window)
            ct = (time.perf_counter() - t0) / n_runs * 1000
            t0 = time.perf_counter()
            for _ in range(n_runs):
                gpu_fn(arr, window)
            gt = (time.perf_counter() - t0) / n_runs * 1000
        winner = "GPU" if gt < ct else "CPU"
        print(f"{name:>20s} {n:>7d} {ct:>10.4f} {gt:>10.4f} {winner:>6s}")
