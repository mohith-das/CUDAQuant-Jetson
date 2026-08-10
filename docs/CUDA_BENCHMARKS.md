# CUDA Benchmarks — CUDAQuant-Jetson

> Real results. Never fabricated. Re-measured 2026-08-09.
> Device: NVIDIA Jetson Orin Nano Super 8GB (nvgpu, SM 8.7)
> JetPack 7.2, CUDA 13.2, Driver 595.78
> Torch: 2.12.0 (Jetson-Orin-Wheels build for CUDA 13.2/SM 8.7)
> CuPy: 14.1.1 (cupy-cuda13x)
> Commit: current

---

## 1. Feature dispatch — crossover thresholds

Empirically measured per-function thresholds where GPU beats CPU.
Below threshold: CPU faster (GPU launch + transfer overhead dominates).
Above threshold: GPU wins.

Measured: `benchmarks/measure_crossover.py`, n_runs=5, window=20.

| Function | Threshold | Why |
|---|---|---|
| rolling_min | **1,000** | CPU O(n·w) loop is pathologically slow; GPU wins early |
| rolling_max | **1,000** | Same as rolling_min |
| rolling_zscore | **20,000** | GPU wins at 20k+ |
| rolling_std | **100,000** | GPU wins at 100k |
| rolling_variance | **100,000** | GPU wins at 100k |
| rolling_mean | ∞ (never GPU) | CPU O(n) cumsum always wins |
| rolling_sum | ∞ (never GPU) | CPU O(n) cumsum always wins |
| returns | ∞ (never GPU) | CPU O(n) trivially fast |

---

## 2. Feature computation — batch GPU speedup

All features computed for 7 window sizes at n=5,000 bars (typical experiment size).

| Mode | Time | GPU calls | CPU calls |
|---|---|---|---|
| Sequential (all CPU) | 99 ms | 0 | 35 |
| Dispatch (auto GPU/CPU) | **24 ms** | 14 | 21 |
| **Speedup** | **4.2x** | | |

Breakdown by function at n=5,000:
| Function | Time | Backend |
|---|---|---|
| rolling_min (7 windows) | 8 ms | GPU |
| rolling_max (7 windows) | 11 ms | GPU |
| rolling_mean (7 windows) | <1 ms | CPU |

---

## 3. GPU ML — logistic regression training

Torch CUDA vs sklearn CPU at n=5,000 samples, 10 features, 200 epochs.
CPU: sklearn LogisticRegression (liblinear solver).
GPU: PyTorch SGD on CUDA.

| Metric | GPU | CPU |
|---|---|---|
| Training time | ~200 ms | ~15 ms |
| Prediction agreement | 99.3% | — |
| Probability correlation | 0.923 | — |
| Accuracy | 98.5% | 98.5% |

**Note:** GPU training is slower than CPU for this model size (sklearn's liblinear is highly optimized for small n). GPU advantage emerges at larger n (100k+ samples) where sklearn's memory usage grows and torch's batched GPU SGD scales better. For the typical experiment sizes in this repo, CPU sklearn is preferred.

---

## 4. Batched experiment engine

Grid search: 4 lookback values × 3 exit_lookback values = 12 combinations,
n=200 bars of 5-min data.

| Mode | Time | Speedup |
|---|---|---|
| Sequential | 11,905 ms | — |
| Batched (pre-computed features) | 11,912 ms | 1.0× |

**No significant speedup from batching** — the backtester walk-forward loop dominates runtime (>99%), not feature computation. Feature pre-computation is ~0.1% of total experiment time at this scale. The batched runner infrastructure is in place for future GPU-backtester acceleration.

---

## 5. GPU vs CPU parity

All dispatched features match CPU reference within documented tolerances.
See `tests/gpu/test_gpu_parity.py` (8/8 passing on Jetson).

---

## Reproduction

All numbers above were reproduced with:
```bash
ssh matt@matt.local
cd ~/code/cudaquant
git log --oneline -1  # verify commit matches
.venv/bin/python benchmarks/measure_crossover.py  # thresholds
.venv/bin/python benchmarks/gpu_benchmark.py       # feature throughput
```

**Previous stale numbers removed.** The old n=100k-only measurements (which showed rolling_zscore 3.4x and rolling_std 2.2x) are superseded by the per-function crossover analysis above.
