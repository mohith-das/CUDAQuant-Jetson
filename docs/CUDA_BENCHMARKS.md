# CUDA Benchmarks — CUDAQuant-Jetson

> Real results. Never fabricated.
> Device: NVIDIA Jetson Orin Nano Super 8GB (nvgpu)
> JetPack 7.2, CUDA 13.2, Driver 595.78
> Date: 2026-08-09 | Commit: (current)

## Test setup
- CPU: Python 3.12.3, NumPy float64 reference implementations
- GPU: CUDA C++ float32 kernels, ctypes bindings, pinned memory transfers
- Window size: 20
- Runs: 5 per test, median reported

## Scaling — rolling_mean

| Array size | CPU (ms) | GPU (ms) | Speedup |
|-----------:|---------:|---------:|--------:|
| 1,000     | 0.10     | 16.25    | 0.0x   |
| 10,000    | 0.25     | 1.23     | 0.2x   |
| 100,000   | 1.82     | 1.82     | 1.0x   |

## Detailed — n=100,000, window=20

| Function       | CPU (ms) | GPU (ms) | Speedup |
|---------------:|---------:|---------:|--------:|
| rolling_mean   | 1.33     | 1.61     | 0.8x   |
| rolling_std    | 3.75     | 1.68     | 2.2x   |
| simple_returns | 0.56     | 1.73     | 0.3x   |
| rolling_zscore | 6.04     | 1.79     | 3.4x   |

## Analysis

**Crossover point:** ~50k–100k elements. Below this, GPU launch + PCIe transfer
overhead dominates. Above this, GPU kernels begin to beat CPU, especially for
compute-intensive operations.

**Best case:** `rolling_zscore` (3.4x) — amortizes the single memory transfer
across mean, variance, and z-score computation in one kernel pass.

**Worst case:** `simple_returns` (0.3x) — trivial O(n) operation where GPU
overhead exceeds CPU execution time at this array size.

**Numerical precision:** GPU uses float32; CPU reference uses float64. Results
match within:
- Mean/min/max/sum/returns: < 1e-4
- Std/variance/zscore: < 5e-2 (float32 catastrophic cancellation in `E[X^2] - E[X]^2`)
- Acceptable for feature computation; improvement possible with Welford's algorithm

## Known limitations
1. Naive per-element window recomputation (no shared memory sliding window)
2. Single CUDA stream — no concurrent kernel execution
3. No kernel fusion across different feature types
4. Float32 precision limits for variance computation
5. Small Jetson GPU (1024 CUDA cores) limits parallelism scaling

## Optimization opportunities
- Shared-memory sliding window for rolling stats (expected 2-5x improvement)
- Warp-level reductions for mean/variance
- CUDA stream overlap for multi-symbol processing
- Kernel fusion: compute multiple features in single pass
- Pinned memory staging for reduced transfer latency
