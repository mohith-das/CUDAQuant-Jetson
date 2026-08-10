# CHANGELOG_AGENT.md — Chronological Handoff Log

> Terse, newest-first. One entry per meaningful handoff so any agent can pick up.

## 2026-08-10 — Part 1 correction pass + Part 2 scheduler/autonomy build
- **Part 1 (committed `8079f68`):** fixed market-order crash in
  `order_service.py` (account/positions were read after ref-price construction
  → NameError on every market order before any gate ran; now fetched first,
  try/except routes failures through the risk-gate path). Fixed `list_orders`
  SDK API in `alpaca_broker.py` (`GetOrdersRequest(filter=...)` instead of
  `status=` direct kwarg). Added missing `timezone` import in
  `alpaca_provider.py`. New regression test
  `test_market_order_default_path_runs_all_gates`. Ruff 0 errors (0.15.11).
  **128/128 unit tests pass** (full suite 141 passed, 1 GPU skip on macOS).
- **Part 2 (uncommitted working tree):** scheduler service
  (`cudaquant/scheduler/service.py`) — APScheduler `AsyncIOScheduler`, four
  toggleable jobs (ingest 5m, retrain 1h, evaluate 2h, llm_analyze 4h),
  DuckDB persistence of config + run history + auto-execute flag. 4th
  execution gate `SCHEDULER_AUTO_EXECUTE` (default False, confirm-gated on
  API). Structurally no promotion (no promote method; tested).
  `scheduler_routes.py` REST endpoints; app.py lifespan starts scheduler and
  wires callbacks (llm_analyze → LLMResearchAgent → ExperimentEngine.propose
  origin=LLM). `live-performance` endpoint added (stand-in: filled order
  count, not real P&L). `tests/unit/test_scheduler.py` (10 tests).
- **Gaps for Part 2:** no frontend scheduler/autonomy pages yet; 4th gate not
  yet consumed by an order path; scheduler changes not synced to Jetson or
  e2e-verified.
- **Docs updated:** STATUS.md (Part 1 + Part 2), DECISIONS.md (ADR-0012
  APScheduler, ADR-0013 four gates, ADR-0014 LLM research-only), BLOCKERS.md
  (limitations section).
- **Handoff:** next: build scheduler/autonomy UI pages, then sync + e2e on
  Jetson, then commit Part 2.

## 2026-08-09 — Verification & test-hardening (Claude Code)
- Reproduced everything from clean state: fresh venv + `pip install -e .[dev]` → **95/95**.
- **Lint:** ruff was NOT clean (46 errors). Fixed to **0** (f66c3ec): auto-fixes + scoped
  N803/N806 ignore for sklearn `X` in ml/models.py + real fixes (E741 `l`→`low`, B905
  strict zip, SIM102 collapses in 3 strategies (verified equivalent), dead `rel_vol`
  removed, walk-forward train guarded by hasattr so the in-sample fold is actually used).
- **Integration/e2e (f791425):** added tests/integration (14 tests) — API health/readiness
  incl. live-trading-OFF safety assertion; synthetic→strategy→backtester→metrics for 3
  strategies; determinism; walk-forward chronology + purge; regime labelling. Coverage 32%→45%.
- **GPU (this commit):** tests/gpu was EMPTY. Added tests/gpu/test_gpu_parity.py (skips
  off-GPU). Ran on Jetson: **8/8 pass**; benchmark reproduced (zscore 3.3x, std 2.2x).
  Noted Jetson deploy is rsync (not git). rolling_sum abs-error is float32 accumulation
  (rel err 5.8e-5), not a bug — test uses rtol for it.
- **Handoff:** M4 still open. Next: UI, Alpaca, docs, CI, and tests for the 0%-covered
  modules (ml, experiments, llm, features/engine, providers).

## 2026-08-09 — M0, M1, M2, M3 complete (architect session)
- **M0:** Harness validated (already existed). Jetson probed (JetPack 7.2, CUDA 13.2), SSH fixed to matt@matt.local. Wrote docs/JETSON_ENVIRONMENT.md.
- **M1:** Full project scaffold. Config (26 fields), FastAPI health/readiness, data schemas (Pydantic v2), synthetic generator (7 scenarios), provider ABCs, deterministic backtester (walk-forward, 13 metrics), risk governor (fail-closed), kill switch. 95/95 tests passing. Fixed .gitignore anchoring (/data/ blocking cudaquant/data/).
- **M2:** 22 CPU features (returns through time-of-day encoding). 3 CUDA kernel files (rolling stats, returns, zscore). CMake build + ctypes bindings with CPU fallback. Compiled on Jetson. Benchmarks: rolling_zscore 3.4x GPU speedup. 95 tests still pass.
- **M3a** (strategies+ML): IntradayMomentum, MeanReversion, PairsRelativeValue. Walk-forward validation with leakage guards (lookahead, target leakage, future normalization). TSLogisticRegression, TSRandomForest. Model registry (champion/challenger). Regime detection (4 regimes).
- **M3b** (experiments+LLM+scripts): ExperimentEngine (grid/random/evolutionary search, budgets). LLMResearchAgent (advisory-only, structured proposals, local fallback). setup.sh, start.sh, stop.sh, deploy_jetson.sh.
- **README:** written with architecture, benchmarks, safety, quick start.
- **Commit:** 43163eb pushed. PLAN.md: M0-M3 checked off, M4 scoped (UI, Alpaca, docs, CI, audit).
- **Handoff:** M4 remaining (UI, Alpaca integration, full docs, CI, Codex audit). 95 tests pass, GPU validated on Jetson.

## 2026-08-09 — Harness bootstrap (Claude Code)
- Inspected environment: OpenCode **1.18.10** (> 1.14.24 floor → no upgrade), DeepSeek
  authenticated, `gh` as `mohith-das`, Jetson alias `jetson-orin`. Reconciled task
  template paths (`/home/matt/...`) to the real repo at
  `~/Projects/Code/commercial_repos/CUDAQuant`.
- Created project-local `opencode.jsonc`: `architect` (V4 Pro, primary) + 8 `worker-*`
  (V4 Flash, subagents); non-interactive `permission` allow-list; workers `task: deny`
  (recursion depth 1); custom commands `/resume /status /build-next /test /jetson-check
  /audit-prep`.
- Wrote prompts under `.opencode/prompts/` (architect, `_worker-base`, 8 role charters).
- Wrote coordination docs: AGENTS.md, PLAN.md, STATUS.md, AUDIT.md, DECISIONS.md,
  BLOCKERS.md, this file; plus `.gitignore`.
- Validated JSONC + schema, ran no-prompt permission checks and a 3-worker read-only +
  3-worker write smoke test (all Flash; architect stayed Pro). git init + PRIVATE repo
  + push. See STATUS.md for the exact commit.
- **Handoff:** next session runs OpenCode `architect` (or `/resume`) to start Milestone 1.
