#!/usr/bin/env python3
"""GPU vs CPU benchmark for CUDAQuant features."""
import numpy as np
import time
from cudaquant.features.gpu.kernels import (
    gpu_rolling_mean, gpu_rolling_std, gpu_simple_returns, gpu_rolling_zscore,
)
from cudaquant.features.engine import (
    rolling_mean as cpu_mean, rolling_std as cpu_std,
    returns as cpu_returns, rolling_zscore as cpu_zscore,
)

n_runs = 5
window = 20

# ── Scaling benchmark ────────────────────────────────────────────────────────
sizes = [1000, 10000, 100000]
print("Scaling benchmark (rolling_mean, window=20):")
print(f"{'Size':>10s}  {'CPU ms':>10s}  {'GPU ms':>10s}  {'Speedup':>8s}")
print("-" * 45)

for n in sizes:
    prices = np.cumsum(np.random.randn(n).astype(np.float32)) + 100.0
    prices64 = prices.astype(np.float64)

    t0 = time.perf_counter()
    for _ in range(n_runs):
        cpu_mean(prices64, window)
    cpu_time = (time.perf_counter() - t0) / n_runs * 1000

    t0 = time.perf_counter()
    for _ in range(n_runs):
        gpu_rolling_mean(prices, window)
    gpu_time = (time.perf_counter() - t0) / n_runs * 1000

    speedup = cpu_time / gpu_time if gpu_time > 0 else 0
    print(f"{n:>10d}  {cpu_time:>10.2f}  {gpu_time:>10.2f}  {speedup:>7.1f}x")

# ── Detailed benchmark (largest size) ────────────────────────────────────────
n = 100000
prices = np.cumsum(np.random.randn(n).astype(np.float32)) + 100.0
prices64 = prices.astype(np.float64)

tests = [
    ("rolling_mean", cpu_mean, gpu_rolling_mean, prices64, prices, window),
    ("rolling_std", cpu_std, gpu_rolling_std, prices64, prices, window),
    ("simple_returns", cpu_returns, gpu_simple_returns, prices64, prices, None),
    ("rolling_zscore", cpu_zscore, gpu_rolling_zscore, prices64, prices, window),
]

print()
print(f"Detailed benchmark (n={n:,}, window={window}, {n_runs} runs):")
print(f"{'Function':>20s}  {'CPU ms':>10s}  {'GPU ms':>10s}  {'Speedup':>8s}")
print("-" * 55)

for name, cpu_fn, gpu_fn, arr_cpu, arr_gpu, w in tests:
    t0 = time.perf_counter()
    for _ in range(n_runs):
        if w:
            cpu_fn(arr_cpu, w)
        else:
            cpu_fn(arr_cpu, False)
    cpu_t = (time.perf_counter() - t0) / n_runs * 1000

    t0 = time.perf_counter()
    for _ in range(n_runs):
        if w:
            gpu_fn(arr_gpu, w)
        else:
            gpu_fn(arr_gpu)
    gpu_t = (time.perf_counter() - t0) / n_runs * 1000

    sp = cpu_t / gpu_t if gpu_t > 0 else 0
    print(f"{name:>20s}  {cpu_t:>10.2f}  {gpu_t:>10.2f}  {sp:>7.1f}x")
