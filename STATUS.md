# STATUS.md — Current Repository State

- **Last updated:** 2026-08-10 (full-stack completion — e2e verified at 0a44707)
- **Current branch:** main (tracks `origin/main`)
- **Remote:** `git@github.com:mohith-das/CUDAQuant-Jetson.git` (PRIVATE)
- **Current commit:** 0a44707 (full-stack)
- **Jetson verified at:** 0a44707 — e2e test script `scripts/e2e_test.sh` run on-device

## Completed: Full-Stack Integration

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

### Phase 5 — Frontend ✅
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

## Tests
- **117/117 unit tests pass** on macOS
- **8/8 GPU parity tests pass** on Jetson
- **8/8 order service safety tests pass**
- Ruff: 0 errors

## Known limitations
- Frontend currently shows "frontend not built" message on Jetson (dist/ not deployed — needs build-then-rsync step)
- RAPIDS cuML blocked by CUDA version (BLOCKERS.md)
- No Alpaca API keys configured (synthetic mode works fully)
- WebSocket auth not enforced at connect time (uses query param or first message)
