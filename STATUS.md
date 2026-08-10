# STATUS.md — Current Repository State

- **Last updated:** 2026-08-10 (Correction Pass 3 committed; crypto support in working tree, uncommitted)
- **Current branch:** main (tracks `origin/main`)
- **Remote:** `git@github.com:mohith-das/CUDAQuant-Jetson.git` (PRIVATE)
- **Current commit:** 9824782 (Correction Pass 3: ModelRegistry persistence, ExperimentEngine singleton, 4th gate wired)
- **Working tree:** NOT clean — uncommitted crypto support (see "Crypto support — working tree" below).
  The tree was observed being actively modified during the docs pass; treat its state as in-flight.
- **Jetson verified at:** 0a44707 — e2e test script `scripts/e2e_test.sh` run on-device
  (Correction Pass 3 + crypto work NOT yet synced to Jetson)

## Correction Pass 3 — committed 9824782 ✅
- **ModelRegistry persistence fixed:** `ModelRegistry(db_path=...)` now receives
  `settings.DUCKDB_PATH` at every call site (`app.py`, `model_routes.py`). Previously the
  API routes and scheduler callback created per-instance registries with no persistence —
  models vanished on restart.
- **ExperimentEngine shared singleton:** new `get_shared_engine(db_path)` in
  `experiments/engine.py`; API routes and scheduler callbacks now share one DB-backed
  instance instead of separate instances that couldn't see each other's data.
- **4th execution gate wired:** new `SchedulerService.execute_champion_signal()`
  (`scheduler/service.py`) runs the full gate chain — Gate 4 (`can_auto_execute()`,
  `SCHEDULER_AUTO_EXECUTE`, default False) first, then Gates 1–3 via
  `order_service.submit_order()` (config, RiskGovernor, KillSwitch). Covered by
  `tests/unit/test_four_gate_chain.py`.
- **`scripts/verify_cleanup.sh` added:** cancels all open Alpaca paper orders and kills
  stray uvicorn processes on test ports. Run at start/end of every verification round.
- **Settings gained `BRAVE_SEARCH_API_KEY`, `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`**
  (config/settings.py) — pydantic `extra=forbidden` was rejecting `.env` values for
  not-yet-declared providers. These are **config fields only**; no search-tool wrapper
  code exists yet (see Known limitations).
- **Tests at this commit:** 144 passed, 1 skipped (full suite, clean env) — 130 unit +
  14 integration + 1 GPU-parity skip off-Jetson. Ruff clean at commit.

## Crypto support — working tree ⏳ (UNCOMMITTED, in-flight)
Crypto support is implemented in the working tree but is **not committed** and was
observed being actively modified during the docs pass (the provider file appeared,
disappeared, and reappeared between commands). Do not treat any of this as done until
committed and re-verified:
- **`cudaquant/providers/alpaca_crypto_provider.py`** — `AlpacaCryptoMarketDataProvider`
  using alpaca-py `CryptoHistoricalDataClient` / `CryptoBarsRequest`; symbols in
  crypto-pair format (`"BTC/USD"`, `"ETH/USD"`); implements the `MarketDataProvider` ABC.
- **Fractional quantities:** `qty` changed `int → float` in `Order`/`Fill`/`Position`
  schemas (also `Bar.volume`/`Trade.size` `int → float`).
- **GTC time-in-force:** `alpaca_broker.py` selects `TimeInForce.GTC` for symbols
  containing `/` (crypto pairs) vs `TimeInForce.DAY` for equities.
- **Caveats observed:** `tests/unit/test_order_service.py::test_order_service_with_fractional_qty`
  currently **FAILS** (it asserts the old `int`-schema rejection; with the float schema,
  pydantic 2.13.4 accepts `qty=0.0234`, so the test's expectation is stale). Ruff reports
  **1 error** (F841 unused `service` in that test). Both are working-tree-only; the
  committed tree is green.
- Full suite in the churned working tree: **149 passed, 1 failed, 1 skipped**.

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

## Part 2 — Scheduler & autonomy build ✅ (committed fbd2d24, 2eda669, 9824782)
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
  explicit `{"confirm": "ENABLE"}` on the API. **Wired** in Correction Pass 3 through
  `execute_champion_signal()` (see above).
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
  run-now. Plus `tests/unit/test_four_gate_chain.py` (5 tests) for the full gate chain.
- **Frontend:** committed — `Scheduler.tsx` and `LLMInbox.tsx` pages + nav routes exist in
  the React app (frontend/src/pages/). Part 2 UI is no longer a gap.

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

### Phase 5 — Frontend ✅ (11 pages)
- React+TypeScript+Vite, 11 pages incl. Scheduler + LLMInbox, lightweight-charts candlestick charts
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

Correction Pass 3 and the working-tree crypto changes have **not** been synced to Jetson
or re-verified on-device.

## Tests
- **Committed HEAD (9824782), clean env:** **144 passed, 1 skipped** full suite
  (130 unit + 14 integration + 1 GPU parity skip off-Jetson). This matches the commit
  message's "130/130" (unit count) — full suite is 145 total.
- **Current working tree (churned):** **149 passed, 1 failed, 1 skipped** — the failure is
  `test_order_service_with_fractional_qty` (stale assertion vs the uncommitted float-qty
  schema; see Crypto section). Not a committed-tree failure.
- **On this Mac, `pytest` from the repo root fails at collection:** the local `.env`
  contains `FMP_API_KEY` and `FINNHUB_API_KEY`, which are not fields of the Settings model
  (pydantic `extra=forbidden`) — Settings() raises before tests run. The working tree adds
  `extra="ignore"` to settings.py to fix this; until then run tests with a clean env or
  remove those keys from `.env`.
- **8/8 GPU parity tests pass** on Jetson (verified at 0a44707)
- **8/8 order service safety tests pass**
- Ruff: 0 errors at HEAD; **1 error in working tree** (F841 in the fractional-qty test)

## Known limitations
- **Crypto support is uncommitted / in-flight** — `alpaca_crypto_provider.py`, float qty,
  and GTC TIF live in the working tree only; the fractional-qty test fails and ruff shows
  one error in that tree. Commit + re-verify before calling crypto done.
- **Search tool wrappers NOT built** — `BRAVE_SEARCH_API_KEY` / `TAVILY_API_KEY` /
  `FIRECRAWL_API_KEY` settings fields exist, but there is no Brave/Tavily/Firecrawl client
  code anywhere in the repo.
- **LLM_API_KEY is effectively unset** — the `.env` value is a placeholder, so
  `LLMResearchAgent` runs in local deterministic fallback mode (no provider configured).
  Documented state, not a blocker.
- **Local `.env` drift** — `FMP_API_KEY` / `FINNHUB_API_KEY` present in `.env` but absent
  from the Settings model break Settings() construction on this Mac (collection errors).
  Working-tree `extra="ignore"` addresses it; not yet committed.
- **live-performance endpoint is a stand-in** — returns filled-order count, not realized P&L
- **Correction Pass 3 + crypto not yet on Jetson** — verified Jetson state is still 0a44707
- RAPIDS cuML RandomForest GPU path still blocked by CUDA version (BLOCKERS.md)
- Live trading stays **OFF by default**; scheduler auto-execute also defaults **OFF**
- WebSocket auth not enforced at connect time (uses query param or first message)
