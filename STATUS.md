# STATUS.md — Current Repository State

- **Last updated:** 2026-08-10 (correction pass — hardware-verified at f3634f7)
- **Current branch:** main (tracks `origin/main`)
- **Remote:** `git@github.com:mohith-das/CUDAQuant-Jetson.git` (PRIVATE)
- **Current commit:** f3634f7 (GPU integration correction pass)
- **Jetson verified at:** f3634f7 (`git rev-parse HEAD` on jetson-orin matches)

## Completed: GPU Integration

### 1. Feature dispatch layer
- `cudaquant/features/dispatch.py`: per-function GPU/CPU routing
- Empirically-measured size thresholds (Jetson Orin, CUDA 13.2):
  - rolling_min/max: GPU at n≥1,000 (CPU O(n·w) loop loses badly)
  - rolling_zscore: GPU at n≥20,000
  - rolling_std/variance: GPU at n≥100,000
  - rolling_mean/sum, returns: never GPU (CPU O(n) always wins)
- Dispatch checks: CUDA_ENABLED config → library loadable → size above threshold
- `get_stats()` for observability (gpu_calls, cpu_calls, bypass reasons)
- Strategies and regimes rewired to use dispatch (was importing engine directly)

### 2. GPU-accelerated ML
- `TSLogisticRegressionGPU`: torch CUDA logistic regression (SGD+BCE+L2)
- Same fit/predict_proba/predict interface as CPU sklearn
- Factory `create_logistic_regression()` auto-selects GPU/CPU
- Verified: 99.3% prediction agreement, 92.3% prob correlation with CPU
- torch: Jetson-Orin-Wheels build (SM 8.7, CUDA 13.2) — no SM 8.7 warning
- cupy: clean cupy-cuda13x (was two conflicting packages)
- RandomForest: CPU-only (RAPIDS blocked by CUDA 12 vs 13.2 incompatibility — BLOCKERS.md)

### 3. Batched GPU experiment engine
- `BatchedExperimentRunner` with pre-computed feature caching
- Honest benchmark: backtester dominates runtime (>99%), feature batching is minor
- Feature computation itself: 4.2x GPU speedup at n=5k (rolling_min/max)

### 4. Honest benchmarks
- `docs/CUDA_BENCHMARKS.md`: fully re-measured, stale numbers removed
- Per-function crossover thresholds with reproduction commands
- ML training parity verified

### 5. Observability
- `/readiness`: reports `gpu_active` (features lib) and `ml_gpu_active` (torch CUDA)
- Can differ from `cuda_enabled` config flag — misconfiguration signal
- `LD_LIBRARY_PATH` baked into setup.sh and start.sh

### 6. Tests
- **123/123 CPU tests pass** on macOS (+ 1 skipped GPU test — expected, no GPU lib on Mac)
- **8/8 GPU parity tests pass** on Jetson at f3634f7 (real hardware, verified — not skipped)
- **ML parity benchmark** runs from committed script: 99.3% agreement, 92.3% prob correlation, 98.5% accuracy
- Ruff: 0 errors (verified)

### 7. Docs
- DECISIONS.md: ADR-0006 (torch wheel), ADR-0007 (dispatch thresholds), ADR-0008 (GPU ML)
- BLOCKERS.md: RAPIDS cuML RandomForest documented with evidence
- CUDA_BENCHMARKS.md: fully re-measured with committed reproduction scripts
- README.md: synced to CUDA_BENCHMARKS.md actual numbers

## Known limitations
- RAPIDS cuML RandomForest: blocked by CUDA 12 vs 13.2 (BLOCKERS.md)
- GPU training slower than sklearn for small n (sklearn liblinear is highly optimized)
- Batched experiment engine: feature pre-computation is minor vs backtester runtime
- No Alpaca API keys (synthetic mode works fully)
- UI not yet built

## Active Work Claims
_(none)_
