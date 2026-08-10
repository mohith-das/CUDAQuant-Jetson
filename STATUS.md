# STATUS.md — Current Repository State

- **Last updated:** 2026-08-09 (architect session end — M0/M1/M2/M3 complete, M4 started)
- **Current branch:** main (tracks `origin/main`)
- **Remote:** `git@github.com:mohith-das/CUDAQuant-Jetson.git` (PRIVATE)
- **Current commit:** 1fc4ad9 (M3 scripts + LLM agent) — run `git log -1 --oneline` for latest
- **Current milestone:** Milestone 3 COMPLETE. Milestone 4 (UI, docs, Alpaca, CI) in progress.

## Completed work summary

### M0 — Harness ✅
OpenCode multi-agent harness (architect + 8 workers), coordination docs, GitHub repo.

### M1 — Project Scaffold ✅
- Python package with pyproject.toml, all dependencies
- Config system (pydantic-settings, 26 fields, live-trading gate)
- FastAPI app with `/health` and `/readiness` endpoints
- Pydantic v2 data schemas (Bar, Order, Fill, Position, Account)
- SyntheticMarketDataGenerator with 7 market scenarios
- Provider ABCs + SyntheticMarketDataProvider
- DeterministicBacktester (walk-forward, costs/slippage/spread, 13 metrics, no-look-ahead)
- RiskGovernor (fail-closed) + file-based KillSwitch
- Strategy ABC + BuyAndHold baseline
- 95/95 unit tests passing

### M2 — GPU Acceleration ✅
- 22 CPU feature functions (returns, rolling stats, RSI, ATR, VWAP, momentum, beta, correlation, etc.)
- 3 CUDA kernel files (.cu): rolling stats, returns, z-score
- CMake build system targeting SM 8.7 (Orin)
- ctypes bindings with graceful CPU fallback (verified on macOS + Jetson)
- Compiled and benchmarked on Jetson Orin (JetPack 7.2, CUDA 13.2)
- Honest benchmarks: rolling_zscore 3.4x GPU speedup at n=100k

### M3 — Strategies, ML, Experiments ✅
- 3 baseline strategies: IntradayMomentum, MeanReversion, PairsRelativeValue
- Walk-forward validation: chronological splits, purge/embargo, leakage detection (lookahead, target leakage, future normalization)
- ML models: TSLogisticRegression, TSRandomForest with chronological training
- Model registry: candidate → challenger → champion → retired lifecycle, DuckDB persistence
- Regime detection: 4 regimes (trending/ranging × high/low vol) with performance attribution
- Experiment engine: lifecycle tracking, grid/random/evolutionary search, budget limits
- LLM research agent: advisory-only, structured proposals, works without API key, local fallback
- Setup/start/stop/deploy scripts (setup.sh, start.sh, stop.sh, scripts/deploy_jetson.sh)

## Work remaining (Milestone 4)
- [ ] UI dashboards (worker-ui)
- [ ] Alpaca provider integration (needs API keys; synthetic works fully)
- [ ] Comprehensive docs (README, architecture, deployment)
- [ ] Integration tests + CI
- [ ] Codex audit prep

## Tests
- **95/95 unit tests passing** on macOS (CPU)
- GPU tests pass on Jetson with documented float32 precision limits
- End-to-end smoke test: strategies + backtester + walk-forward + regime detection verified

## Jetson deployment state
- **SSH:** matt@matt.local (alias jetson-orin)
- **Code synced** to ~/cudaquant/
- **CUDA compiled:** libcudaquant_kernels.so (141 KB)
- **Python deps:** installed in .venv/ (fastapi, pandas, numpy, scikit-learn, duckdb, pyarrow, etc.)
- **GPU validation:** passed (mean/min/max/sum/returns < 1e-4; std/var < 5e-2)
- **Benchmarks:** recorded in docs/CUDA_BENCHMARKS.md (rolling_zscore 3.4x speedup)

## Known limitations
- Float32 GPU precision limits for variance/std (documented)
- GPU overhead dominates for n < ~50k
- No Alpaca API keys (synthetic mode works fully)
- No LLM API key (LLM agent works with local fallback)
- UI not yet built (M4)

## Active Work Claims
_(none)_
