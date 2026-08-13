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

## Milestone 4 — UI, deployment, docs ✅
- [x] Single-user UI dashboards + system/risk pages (worker-ui) — 13 routes, SPA fallback, tokens.css, ErrorBoundary
- [x] Jetson deployment/runbook (worker-docs) + benchmark presentation
- [x] README + architecture + deployment docs (worker-docs) — safety + paper/live switching
- [x] Alpaca provider integration (alpaca-py 0.43.5: market data + broker, GTC/float qty, crypto) — needs API key; synthetic mode works fully
- [x] Integration tests + CI — 234/1 + 8 GPU, ruff 0, restart-survival tests
- [x] First independent Codex audit pass (see AUDIT.md) — AUDIT-001..022 verified
- [x] Persistent paper/live toggle — TradingModeService (desired/effective, DuckDB, boot fail-safe), PUT /api/risk/trading-mode, Execution toggle UI (334d416 deployed at 198716c)

## Milestone 5 — Market Intelligence & Universe (actionable UI, part 1)
> Gap verified 2026-08-13 via 14 live screenshots: Dashboard has only kill-switch, Data has AAPL-only chart, Experiments/LLM Inbox are read-only tables, Models shows 60 clones, Regimes is a single button — no market overview, no search, no universe, no training picker, no LLM apply, no champion signal loop. This milestone makes the UI actionable.

- [x] **5a — Market search + stock info** — `GET /api/data/search?q=` (FMP/Finnhub with synthetic fallback, cached), `GET /api/data/{symbol}/info` (quote + profile + fundamentals panel), wiring the existing `FMPProvider`/`FinnhubProvider` (currently orphaned) behind the new routes (worker-data: providers; worker-backend: routes; worker-tests: integration)
- [x] **5b — Universe (watchlist) CRUD** — `Universe` entity persisted in DuckDB (`universes` table, owner=request is single-user), `GET|POST|PUT|DELETE /api/universe` + `POST /api/universe/{id}/symbols`, shared singleton pattern; used as default `symbols` source everywhere (worker-data: storage + model; worker-backend: routes)
- [x] **5c — Market page + DataExplorer multi-symbol** — new `frontend/src/pages/Market.tsx` (search bar, quote card, info panel, universe manager, add-to-universe), DataExplorer multi-symbol + universe dropdown (worker-ui)

## Milestone 6 — Training Studio
- [x] **6a — Training service** — `cudaquant/ml/training.py` + `training_runs` DuckDB table: `POST /api/training/run {symbols|universe_id, model_family: logreg|random_forest, features:[22], horizon, test_split}` → `TrainingRun` (candidate in ModelRegistry), feature-matrix via dispatch layer, leakage guards, persisted metrics (worker-ml)
- [x] **6b — Training Studio UI** — `frontend/src/pages/Training.tsx` (universe picker, model-family toggle, 22 feature checkboxes grouped by category, horizon/split controls, run button + history table, link to Model Compare) (worker-ui)

## Milestone 7 — LLM Recommendation Loop
- [ ] **7a — Structured proposal** — extend `ExperimentProposal` with `strategy|model_family|symbols` + feed real champion metrics/regime/universe into `llm_analyze` context; `POST /api/experiments/{id}/apply` → creates a `TrainingRun` + backtest (worker-ml + worker-backend)
- [ ] **7b — LLM Inbox Apply** — inbox row action `Apply` + experiment detail drawer (reasoning, failed modes, metrics_to_evaluate) (worker-ui)

## Milestone 8 — Paper Execution Loop
- [ ] **8a — Champion signal job** — `paper_trade` APScheduler job: champion model → signal on live bars (provider) → `execute_champion_signal()` through all 4 gates; `GET /api/execution/signals` log; real `live-performance` (realized P&L vs backtest maxDD, not just fill count) (worker-quant + worker-backend)
- [ ] **8b — Execution deploy surface** — Execution page `Deploy champion (paper)` toggle + signal log table + Dashboard live P&L pill (worker-ui)

> **Execution order:** 5a (providers) + 6a (training service) can start in parallel (disjoint files: `providers/**` vs `ml/**`). 5b (universe routes) follows 5a. UI (5c, 6b, 7b, 8b) follows its backend slice. Architect owns `DECISIONS.md`/`PLAN.md`/`STATUS.md`/`AUDIT.md`.

_The next OpenCode session owns execution from Milestone 5 onward._
