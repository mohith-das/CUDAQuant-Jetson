# STATUS.md — Current Repository State

- **Last updated:** 2026-08-11 (Muse Spark audit, MCP fix)
- **Current branch:** main (tracks `origin/main`)
- **Remote:** `git@github.com:mohith-das/CUDAQuant-Jetson.git` (PRIVATE)
- **Current commit:** 555b9cb (MCP FastMCP fix + audit reconciliation)
- **Prior verified HEAD:** 6952c86 (Telegram interactive bot + design pass, screenshots)
- **Working tree:** clean (after 555b9cb); `docs/claude_export_temp.md` untracked export only
- **Jetson verified at:** 0a44707 (scripts/e2e_test.sh) — commits after 0a44707 NOT yet synced or e2e-verified on-device
- **Local tests:** 200 passed, 1 skipped (1 GPU parity skip off-Jetson), ruff 0 — `pytest -q` 2026-08-11 on macOS 3.12.12
- **MCP:** 3/3 integration tests now pass after FastMCP fix (was 3 failures at 6952c86)

## What is DONE and verified (local)

- **M0-M3** scaffold, 22 CPU features, 3 CUDA kernels, strategies, walk-forward, ML, registry, regimes, experiments, risk/kill-switch — all persistent via DuckDB with shared singletons (ExperimentEngine, ModelRegistry, LLMResearchAgent via get_shared_*)
- **GPU dispatch** — thresholds min/max≥1k, zscore≥20k, std/var≥100k, mean/sum/returns never GPU; /readiness shows gpu_active vs cuda_enabled (ADR-0007, docs/CUDA_BENCHMARKS.md re-measured)
- **Torch** — Shattered217 wheel for SM 8.7/CUDA 13.2, single cupy-cuda13x (ADR-0006); RAPIDS cuML blocked (BLOCKERS.md)
- **Alpaca** — market data + broker (alpaca-py 0.43.5), crypto provider (BTC/USD pairs), float qty, GTC for crypto (ADR-0015/0016)
- **Order execution** — 4-gate chain (config→RiskGovernor→KillSwitch→SCHEDULER_AUTO_EXECUTE), paper-only default, kill-switch file-based
- **Scheduler** — 4 APScheduler jobs (ingest/retrain/evaluate/llm_analyze) persisted + 4th gate + llm propose→engine (origin LLM/LLM_FALLBACK)
- **Research** — Brave/Tavily/Firecrawl tools + SearchBudget/cache (1h TTL), FMP/Finnhub providers, LLMResearchAgent tool-calling via DeepSeek with budget
- **Control API** — 9 REST modules (/api/data,strategies,backtests,experiments,models,regimes,risk,execution,system) + WS /ws/events, AUTH_TOKEN fail-closed on LAN
- **Frontend** — 13 routes (Dashboard, Data, StrategyLab, Experiments, LLM Inbox, Models, Model Compare, Regimes, Execution, Scheduler, Chat, System, Settings), React+TS Vite + TanStack Query, lightweight-charts 5.2.0 (CandlestickSeries via chart.addSeries), tokens.css design system, ErrorBoundary, SPA fallback (FastAPI catch-all), static assets via /assets mount, App.css correctly imported (19bb825 fix)
- **Chat + MCP + Telegram** — /api/chat read-only tools + separate budget, MCP FastMCP stdio (READ 13 + WRITE 6 via platform_tools/registry.py), Telegram bot polling + inline buttons + @cudaquant mention, 3 alert triggers (kill-switch, job failure, challenger ready)
- **Storage** — storage/db.py read_only=True for readers, no WAL PRAGMA (DuckDB incompatibility fixed at a0b7ad1), fail-loud propagation (7db327c), conftest.py pytest_configure isolation, restart-survival tests (4 tests)
- **Infisical + Tailscale** — INFISICAL_TOKEN in .env/Infisical dev, secrets injected via `infisical run --token ... --env=dev`, server bound to Tailscale IP 100.109.22.68:8000 (not LAN 0.0.0.0), systemd template uses EnvironmentFile=.env (requires manual sudo install)

## What the last local UI audit saw (2026-08-11, headless via 127.0.0.1:8765 with auth)

- **SPA:** all routes return 200 HTML (was 404 before catch-all)
- **13 routes:** all render nav (count 1), no pageerror crashes — Data Explorer now renders 7 canvas elements (was TypeError addCandlestickSeries before fix)
- **Design tokens:** loaded (--bg:#0B0D11 --accent:#2E9BFF via App.css), dark theme, sidebar, pills
- **Auth:** localStorage api_auth_token set → API calls succeed; without token /api/* 401 as designed
- **Remaining visual note:** /scheduler shows "Next run: Invalid Date" on job cards (null→str(None) parsing), /execution order colors now correct after enum .value fix, Strategy Lab schema form + DataExplorer chart + LLM inbox breakdown all present in code (not re-screenshotted with live data this pass)

## What is NOT yet user-ready (needs next architect passes)

- **Docs stale before 555b9cb** — now reconciled here, but Jetson not yet synced; README/CUDA_BENCHMARKS cover 0a44707 numbers, need re-measure after Jetson pull
- **No first-run wizard** — new user must edit .env + run setup.sh + know Tailscale IP; UI empty states hint but no guided Data→Strategy→Backtest→Experiment→Promotion flow
- **live-performance stub** — returns filled order count, not real P&L/drawdown vs backtest; UI Model Compare shows it as "live" but it's incomplete for promotion decisions
- **Unattended not soaked** — scheduler tested in bursts, never multi-day; systemd still manual (BLOCKERS.md sudo), Telegram chat_id live (6369764765) but verify_cleanup port-range narrow (8765-8779) vs pgrep
- **WebSocket auth** at connect time, delete endpoints for experiments/models, and finance-data UI exposure are still stubs
- **Strategy edge unproven** — last real backtest sharpe -0.091 on synthetic; no paper track record; expectation management needed

## Tests

- **Local (555b9cb):** 200 passed, 1 skipped, ruff 0, 67 warnings (datetime.utcnow deprecations)
- **Jetson (0a44707):** 8/8 GPU parity pass, e2e 8 checks (health/readiness/system/strategies/backtest/dashboard/GPU dispatch/experiments) — needs re-run after pull to 555b9cb
- **Coverage:** 32%→45%→188 tests era; MCP + platform_tools still 0% before this fix (now 3 MCP tests)
