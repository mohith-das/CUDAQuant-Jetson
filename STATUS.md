# STATUS.md — Current Repository State

- **Last updated:** 2026-08-09 (architect session, M2 complete → starting M3)
- **Current branch:** main (tracks `origin/main`)
- **Remote:** `git@github.com:mohith-das/CUDAQuant-Jetson.git` (PRIVATE)
- **Current commit:** 7e194ec (M2 GPU acceleration) — run `git log -1 --oneline` for latest
- **Current milestone:** Milestone 2 COMPLETE. Next: Milestone 3 (data providers + ML + strategies).

## Completed work
- **M0:** Harness bootstrap, AGENTS.md, coordination docs, GitHub repo
- **M1:** Full project scaffold — config, FastAPI, data schemas, synthetic provider, deterministic backtester, risk governor, kill switch. 95 unit tests passing.
- **M2:** GPU acceleration — 22 CPU feature functions, 3 CUDA kernel files (.cu), CMake build system, ctypes bindings with graceful CPU fallback. Compiled and benchmarked on Jetson Orin. Honest benchmarks in docs/CUDA_BENCHMARKS.md.

## Work in progress
- Planning Milestone 3 (strategies, walk-forward validation, ML, regimes, experiments, LLM).

## Next actions (Milestone 3)
1. Implement baseline strategies (intraday momentum, mean reversion, pairs/relative value)
2. Walk-forward validation framework + strict time-series leakage guards
3. ML models (logistic regression, random forest) + model registry
4. Regime detection (volatility, trend, volume, correlation-based)
5. Experiment engine + champion/challenger management
6. LLM research agent provider (stub, works without API key)

## Tests
- **95/95 unit tests passing** on macOS (CPU only)
- GPU tests pass on Jetson with documented float32 precision limits
- Benchmark results: rolling_zscore 3.4x GPU speedup at n=100k

## Jetson deployment state
- **SSH accessible** at matt@matt.local (alias jetson-orin)
- **Code synced** to ~/cudaquant/
- **CUDA compiled** — libcudaquant_kernels.so built and validated
- **Python deps** installed in .venv/
- **GPU validation** passed (mean, min, max, sum, returns within 1e-4; std/var within 5e-2)

## Known failures / limitations
- Float32 precision limits for GPU variance/std computation (documented)
- GPU overhead dominates for n < ~50k (crossover point documented)
- No Alpaca API keys configured (Milestone 3+)
- No LLM API key configured (optional, everything works without)

## Active Work Claims
_(none — between milestones)_
