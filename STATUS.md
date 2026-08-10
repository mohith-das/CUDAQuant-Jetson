# STATUS.md — Current Repository State

- **Last updated:** 2026-08-10 (Part 1 correction committed; Part 2 scheduler/autonomy build in working tree)
- **Current branch:** main (tracks `origin/main`)
- **Remote:** `git@github.com:mohith-das/CUDAQuant-Jetson.git` (PRIVATE)
- **Current commit:** 8079f68 (Part 1 correction: market order crash + list_orders SDK + ruff clean)
- **Part 2 (scheduler/autonomy):** uncommitted working-tree changes — see below. Not yet on Jetson.
- **Jetson verified at:** 0a44707 — e2e test script `scripts/e2e_test.sh` run on-device

## Part 1 — Correction pass ✅ (committed 8079f68)
- **Market order crash fixed:** `order_service.py` fetched `account`/`positions` only after
  building the ref-price payload, so every market order (no `limit_price`) hit a NameError
  before any gate ran. Account state is now fetched first, wrapped in try/except that fails
  the order through the risk-gate path.
- **list_orders SDK API fixed:** `alpaca_broker.py` called `get_orders(status=..., limit=...)`
  with status as a direct kwarg — wrong alpaca-py SDK signature. Now uses
  `GetOrdersRequest(status=..., limit=...)` passed as `filter=`.
- **Missing `timezone` import** in `alpaca_provider.py` added.
- **New regression test** `test_market_order_default_path_runs_all_gates` — the market-order
  path (the default API path) previously had zero coverage.
- **Ruff: 0 errors** (verified with ruff 0.15.11).
- **Tests: 128/128 unit tests pass** on macOS; full suite 141 passed, 1 skipped (GPU parity
  test skips off-Jetson).

## Part 2 — Scheduler & autonomy build ⏳ (uncommitted working tree)
- **`cudaquant/scheduler/service.py`** — `SchedulerService` on **APScheduler
  `AsyncIOScheduler`** with four toggleable jobs:
  - `ingest` (every 5 min) — fetch bars from configured provider
  - `retrain` (every 1 h) — train a new candidate on latest data
  - `evaluate` (every 2 h) — walk-forward evaluate challengers vs champion
  - `llm_analyze` (every 4 h) — run LLMResearchAgent, auto-enqueue proposal
- **DuckDB persistence** — job cadences, enabled flags, run history, and the auto-execute
  flag survive restarts (`scheduler_state` table via `storage.db`).
- **4th execution gate:** `SCHEDULER_AUTO_EXECUTE` (`auto_execute_enabled`, default **False**)
  via `SchedulerService.can_auto_execute()` — an independent gate *on the scheduler layer*,
  additional to OrderService's three (config, RiskGovernor, KillSwitch). Enable requires
  explicit `{"confirm": "ENABLE"}` on the API. Not yet wired into `OrderService.submit_order`
  (no autonomous order path exists yet — the gate is enforced by the scheduler API and covered
  by tests).
- **Scheduler is structurally incapable of auto-promotion:** no `promote` method exists on
  the service; jobs and callbacks are promotion-free (tested). Champion promotion remains a
  human UI action.
- **REST routes** (`cudaquant/api/routes/scheduler_routes.py`, bearer-authed):
  `GET /api/scheduler/`, `PUT /api/scheduler/jobs/{name}`, `POST /api/scheduler/jobs/{name}/run-now`,
  `PUT /api/scheduler/auto-execute` (confirm-gated), `DELETE /api/scheduler/auto-execute`.
- **App wiring** (`app.py` lifespan): scheduler started on API startup, callbacks wired —
  ingest→synthetic generator, retrain→train LR candidate into ModelRegistry, evaluate→count
  champion/challenger, llm_analyze→`LLMResearchAgent.propose_experiment()` →
  `ExperimentEngine.propose(origin=LLM)`.
- **Live-performance endpoint:** `GET /api/models/{model_id}/live-performance`
  (`model_routes.py`) — returns filled-order count from OrderService plus stored backtest
  metrics. **Stand-in only** — not real P&L tracking yet.
- **Tests:** `tests/unit/test_scheduler.py` (10 tests) — 4th-gate default-off/on/off,
  auto-promotion impossibility (no method, no callback, no job), config persistence,
  run-now.
- **Frontend:** NOT yet updated — no scheduler/autonomy UI pages, no nav routes. 8 pages
  unchanged. This is the known gap for Part 2 completion.

## Completed: Full-Stack Integration (prior milestones, still true)

### Phase 1 — Alpaca integration ✅
- AlpacaBroker + AlpacaMarketDataProvider (alpaca-py 0.43.5)
- OrderService: single sanctioned order entry with 3 gates
- 8/8 safety tests: config gate, RiskGovernor, KillSwitch all independently verified

### Phase 2 — Experiment persistence ✅
- ExperimentEngine persists to DuckDB, survives restarts

### Phase 3 — Control API ✅
- 9 REST route modules: data, strategies, backtests, experiments, models, regimes, risk, execution, system
- WebSocket: /ws/events for dispatch stats + event broadcast
- All routes tested via FastAPI TestClient

### Phase 4 — Auth & networking ✅
- API_AUTH_TOKEN required on non-loopback binds
- Fail-closed: refuses to start on 0.0.0.0 without token
- Bearer auth on all /api/* and /ws/* routes

### Phase 5 — Frontend ✅ (8 pages; scheduler pages pending)
- React+TypeScript+Vite, 8 pages, lightweight-charts candlestick charts
- Built and verified (TypeScript strict, ESLint clean)
- Served as static files by FastAPI at /

### Phase 6 — Deploy ✅
- frontend built on dev machine, shipped as static bundle (no Node on Jetson)
- scripts/e2e_test.sh for end-to-end verification

## End-to-End Verification (Jetson, 0a44707)
Pasted from `scripts/e2e_test.sh` run on jetson-orin:

1. HEALTH: `{"status":"ok","version":"0.1.0"}` ✅
2. READINESS: `{"gpu_active":true,"ml_gpu_active":true,"trading_mode":"paper"}` ✅
3. SYSTEM: `{"cuda_enabled":true,"gpu_active":true,"ml_gpu_active":true}` ✅
4. STRATEGIES: 3 strategies with introspected parameter schemas ✅
5. BACKTEST: 310 trades, sharpe=-0.091, max_drawdown=0.029 ✅
6. DASHBOARD: served at / ✅
7. GPU DISPATCH: 2,180 GPU calls on rolling_min/max ✅
8. EXPERIMENTS: list works ✅

Part 2 scheduler changes have **not** been synced to Jetson or re-verified on-device.

## Tests
- **128/128 unit tests pass** on macOS (includes 10 new scheduler tests + market-order regression)
- **141 passed, 1 skipped** full suite on macOS (skip = GPU parity test, requires Jetson)
- **8/8 GPU parity tests pass** on Jetson (verified at 0a44707)
- **8/8 order service safety tests pass**
- Ruff: 0 errors (ruff 0.15.11)

## Known limitations
- **Part 2 has no UI yet** — scheduler/autonomy pages and nav routes are not built; frontend
  still shows the original 8 pages
- **live-performance endpoint is a stand-in** — returns filled-order count, not realized P&L
- **4th gate not yet wired to an order path** — `can_auto_execute()` is enforced at the
  scheduler API and covered by tests, but no autonomous order submission exists to consume it
- RAPIDS cuML RandomForest GPU path still blocked by CUDA version (BLOCKERS.md)
- Live trading stays **OFF by default**; scheduler auto-execute also defaults **OFF**
- WebSocket auth not enforced at connect time (uses query param or first message)
