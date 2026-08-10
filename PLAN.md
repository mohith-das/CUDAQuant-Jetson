# PLAN.md — Canonical Roadmap (CUDAQuant-Jetson)

> The architect maintains this file. Check items off only when they are **actually**
> true in the repo (verified by tests/inspection), not when a worker claims done.

## Milestone 0 — Harness bootstrap ✅ (this setup)
- [x] OpenCode multi-agent harness configured (`opencode.jsonc`)
- [x] DeepSeek V4 Pro architect + 8 V4 Flash workers
- [x] Non-interactive permissions; worker recursion disabled
- [x] Coordination docs created
- [x] Repo git-initialized and pushed to PRIVATE GitHub
- [x] Multi-agent smoke test (read-only + write) validated

## Milestone 1 — Project scaffold ✅
- [x] Python project scaffold (`cudaquant/` package, `pyproject.toml`/deps, `tests/`)
- [x] Config system + `.env.example` (secrets from env only)
- [x] FastAPI app shell with health/readiness (worker-backend)
- [x] Data schemas + synthetic data generator (worker-data)
- [x] Deterministic CPU backtester skeleton + determinism test (worker-quant, worker-tests)
- [x] Risk governor + kill switch interfaces, live-trading OFF by default (worker-quant)
- [x] CI-style local test target (`pytest`) green — 95/95 pass

## Milestone 2 — GPU acceleration ✅
- [x] CUDA build setup for Jetson Orin (CMakeLists.txt, build.sh, 3 kernel files)
- [x] CPU feature engine (22 functions: returns, rolling stats, RSI, ATR, VWAP, momentum, etc.)
- [x] GPU feature kernels (rolling mean/std/var/min/max/sum, returns, z-score)
- [x] GPU bindings with graceful CPU fallback (verified on macOS + Jetson)
- [x] CPU/GPU parity tests pass (rolling_zscore 3.4x speedup at n=100k)
- [x] Jetson build + GPU tests + benchmarks recorded in docs/CUDA_BENCHMARKS.md

## Milestone 3 — Data providers & ML ✅
- [x] Baseline strategies: intraday momentum, mean reversion, pairs/relative value
- [x] Walk-forward validation: chronological splits, purge/embargo, leakage guards
- [x] ML models: TSLogisticRegression, TSRandomForest, feature prep, target prep
- [x] Model registry: candidate → challenger → champion → retired lifecycle with DuckDB
- [x] Regime detection: 4 regimes (trending/ranging × high/low vol) with performance attribution
- [x] Experiment engine: lifecycle tracking, grid/random/evolutionary search, budget limits
- [x] LLM research agent: advisory only, structured proposals, works without API key
- [x] Setup/start/stop/deploy scripts verified

## Milestone 4 — UI, deployment, docs
- [ ] Single-user UI dashboards + system/risk pages (worker-ui)
- [ ] Jetson deployment/runbook (worker-docs) + benchmark presentation
- [ ] README + architecture + deployment docs (worker-docs)
- [ ] Alpaca provider integration (needs API key; synthetic mode works fully)
- [ ] Integration tests + CI
- [ ] First independent Codex audit pass (see AUDIT.md)

_The next OpenCode session owns execution from Milestone 1 onward._
