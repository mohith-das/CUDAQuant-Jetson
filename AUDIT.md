# AUDIT.md — Independent Review Ledger

> Auditor: Muse Spark (successor to Claude audit session). This file is the **single continuity record** for all independent verification. The architect reads this at startup and fixes `OPEN` before new features. Built from `docs/claude_export_temp.md` (10,794 lines, 2026-08-09 to 2026-08-11) + fresh verification at HEAD `6952c86`.

## Statuses
`OPEN` → `IN_PROGRESS` → `FIXED_PENDING_VERIFICATION` → `VERIFIED` | `WONT_FIX`

## Finding template
```
AUDIT-XXX
Severity:            <critical | high | medium | low>
Status:             <OPEN | IN_PROGRESS | FIXED_PENDING_VERIFICATION | VERIFIED | WONT_FIX>
Found by:           <auditor>
Commit inspected:   <hash>
Problem:            <what is wrong>
Evidence:           <file:line, test output, repro>
Required fix:       <what must change>
Resolution:         <what was done>
Verified by:        <who/what>
Verification commit:<hash>
```

## Session-0 — Harness bootstrap (Claude Code) — VERIFIED

## Scope history (for continuity)
- **M0** Harness (opencode.jsonc, 8 workers, AGENTS.md) — VERIFIED at 1.18.10, 3-worker parallel smoke test.
- **M1-M3** Scaffold, GPU kernels (3 .cu, libcudaquant_kernels.so), 22 CPU features, strategies, walk-forward, ML, registry, regimes, experiments, LLM, risk governor/kill-switch — 95/95 tests.
- **Verification hardening** — ruff 46→0, coverage 32%→45% (added 14 integration), tests/gpu empty→ 8/8 parity, rsync→git clone at ~/code/cudaquant, JetPack 7.2/CUDA 13.2/SM 8.7 real benchmark (zscore 3.3x, std 2.2x).
- **GPU Dispatch Integration** (Milestone a) — dispatch.py with per-function thresholds (min/max≥1k, zscore≥20k, std/var≥100k, mean/sum/returns never GPU), get_stats(), /readiness gpu_active vs cuda_enabled, LD_LIBRARY_PATH fix. Later extended to full GPU integration with torch ML + batched runner.
- **Torch/Cupy fix** — generic PyPI torch lacks SM 8.7 → switched to `Shattered217/Jetson-Orin-Wheels` torch-2.12.0 cp312 aarch64; cupy-cuda11x+cuda12x conflict → single cupy-cuda13x. (ADR-0006)
- **Full-Stack (Phases 1-7)** — AlpacaMarketDataProvider/Broker (alpaca-py 0.43.5), OrderService 3-gate chain, 9 REST modules + WS, AUTH_TOKEN fail-closed, React+TS Vite 8 pages (later 11), lightweight-charts, off-device build.
- **Scheduler & Autonomy** — APScheduler 4 jobs (ingest 5m/retrain 1h/evaluate 2h/llm_analyze 4h), DuckDB persistence, 4th gate SCHEDULER_AUTO_EXECUTE default False, live-performance stub, 3 new UI pages.
- **Research tools** — Brave/Tavily/Firecrawl clients + SearchBudget/cache, FMP/Finnhub wrappers, TelegramAlerter (3 triggers).
- **Platform layer** — platform_tools/ 13 READ + 5 WRITE, /api/chat (read-only, separate budget), MCP server (stdio), Telegram interactive (polling, buttons, @cudaquant).
- **UI hardening** — SPA fallback, broker pills, LLM inbox, StrategyLab schema form, DataExplorer candlestick, tokens.css design system, ErrorBoundary, progress counters.

---

## Findings — verified history (CLOSED)

### AUDIT-001 — Ruff 46 errors, coverage 32%, empty tests/gpu — VERIFIED
- Severity: medium | Found by: Claude verify @ f66c3ec | Commit: pre-f66c3ec
- Evidence: `ruff check .` 46 errors (I001, N803/N806 on ml X, E741 l, B905, SIM102, F841 dead train_data/rel_vol), `pytest --cov` 32% (strategies/ml/regimes/experiments/llm/api 0%), `ls tests/gpu/` empty.
- Fix: per-file-ignores for sklearn X, dead rel_vol removed, walk-forward train guarded, 14 integration e2e, `tests/gpu/test_gpu_parity.py` (skips off-GPU). Result 109/109 (now 188-197), ruff 0, coverage 45%→.
- Verified: fresh venv 95→109, Jetson 8/8 parity, benchmark reproduced (zscore 3.3x).

### AUDIT-002 — GPU kernels never called — VERIFIED
- Severity: high | Commit: pre-dispatch
- Evidence: `grep -r gpu_rolling cudaquant/` only in tests/benchmarks; `strategies/implementations.py:10` + `regimes/detector.py:14` import engine directly.
- Fix: `cudaquant/features/dispatch.py` with measured thresholds, `get_stats()`, rewired consumers, `benchmarks/measure_crossover.py` sweeps 220/1k/10k/100k, docs/CUDA_BENCHMARKS.md.
- Verified: dispatch stats in readiness, Jetson crossover numbers.

### AUDIT-003 — Generic torch SM 8.7 unsupported + dual cupy — VERIFIED
- Severity: high | Evidence: `python -c "import torch"` warning SM 8.7 not in 8.0,9.0,10.0,11.0,12.0; cupy warns cupy-cuda11x+cupy-cuda12x both installed.
- Fix: switch to Shattered217 wheel, single cupy-cuda13x, pyproject gpu extra comment (ADR-0006).
- Verified: no warning, `torch.cuda.is_available()` True, trivial GPU op OK.

### AUDIT-004 — GPU integration report divergence — VERIFIED
- Severity: high | Commit: a467bcc vs Jetson 126b2b7
- Evidence: md5 mismatch dispatch.py/gpu_models.py/runner.py, Jetson 3 commits behind, 99.3% prose-only, runner _feature_cache dead (never read), I001 in measure_crossover, README 3.4x stale.
- Fix: re-pull f3634f7, add `benchmarks/ml_gpu_parity.py` with cmd in doc, remove dead cache or doc it, ruff --fix, sync README.
- Verified: 126b2b7→f3634f7 pull, ml_gpu_parity 99.3%/0.9227, runner no cache, ruff 0, README sync, 123/1 skip.

### AUDIT-005 — Order execution crashes — VERIFIED
- Severity: critical | Commit: 0a44707
- Evidence: `order_service.py:73` ref price uses account/positions before assignment at 86-87 → market order (default) NameError 500 before any gate; `alpaca_broker.py:list_orders()` passes status= kwarg → TypeError; tests only used LIMIT.
- Fix: reorder fetch before ref_price, use GetOrdersRequest(filter=), add market-order gate test, ruff 26→0, sync BLOCKERS.
- Verified: live POST market AAPL → 500 before, 200 after; list_orders 200 with real paper order ID.

### AUDIT-006 — Persistence staleness (registry + experiment) + 4th gate not wired — VERIFIED
- Severity: critical | Evidence: ModelRegistry()` no db_path → dict-only, POST /api/scheduler/jobs/retrain/run-now → GET /api/models/ [] (no models table); ExperimentEngine import-time singleton vs scheduler per-run instance → DuckDB row d94df758 invisible via API; SCHEDULER_AUTO_EXECUTE only in test.
- Fix: pass storage/db DuckDB path at all ModelRegistry sites, share singleton get_shared_engine(), wire execute_champion_signal() 4-gate chain, verify_cleanup.sh, extra="ignore" for FMP.
- Verified: retrain → GET models shows model, llm_analyze → GET experiments shows origin=llm, 4-gate test, cleanup.

### AUDIT-007 — Crypto support gaps (design reviewed) — VERIFIED (pre-impl)
- Severity: medium | Evidence: StockHistoricalDataClient only, Order.qty int truncates 0.0234 BTC→0, TimeInForce.DAY wrong for 24/7, symbol "BTC/USD" format.
- Fix: AlpacaCryptoMarketDataProvider (CryptoHistoricalDataClient), qty float, GTC for "/" symbols, paper crypto e2e.
- Status: implemented in working tree at 3ff2deb time, later committed (see AUDIT-012).

### AUDIT-008 — Search budget/cache shared-state bug — VERIFIED
- Severity: medium | Evidence: app.py scheduler callback new LLMResearchAgent()→ new SearchBudget() per invocation → cap/cache never accumulate.
- Fix: get_shared_llm_agent() singleton + SearchCache DuckDB 1h TTL, same pattern as engine/registry.
- Verified: 3 back-to-back calls 1→2→3 accumulation.

### AUDIT-009 — Older mislabeled LLM records — VERIFIED
- Severity: low | Evidence: 2ebff72c verbatim _default_proposal(), 9dc0cc32 empty hypothesis both origin=llm.
- Fix: distinct LLM_FALLBACK origin, came_from_llm bool, relabel rows or BLOCKERS note.
- Verified: new records distinguishable; old rows relabeled in later pass (AUDIT-013).

### AUDIT-010 — Systemic 34-class audit incomplete — VERIFIED (later revised)
- Evidence: model_routes fresh OrderService→RiskGovernor per call, AlpacaMarketDataProvider/TelegramAlerter/db.get_connection() uncovered, etc. Later corrected in AUDIT-016.

### AUDIT-011 — Server crash + LLM happy path 0/3 — VERIFIED
- Severity: high | Evidence: live server died mid-verify (no log), 3 DeepSeek calls all fallback (max_tokens=500 truncation).
- Fix: exc_info logging, systemd Restart=on-failure, max_tokens 800 + prompt fix, 1 real happy path pasted.
- Verified: reproduced happy path twice after fix.

### AUDIT-012 — Systemd false claim + stale records still wrong + DB lock — VERIFIED
- Severity: high | Commit: Correction Pass 6 report
- Evidence: cudaquant.service never installed (no unit), template hardcodes HOST=127.0.0.1 API_AUTH_TOKEN=change-me → would revert Tailscale auth; records still llm; WAL PRAGMA not in ADR-0018; test_api_health sets DUCKDB_PATH after Settings() imported.
- Fix: EnvironmentFile=.env, manual step docs, UPDATE rows, conftest.py pytest_configure hook.
- Verified: but next round found WAL invalid (see AUDIT-013).

### AUDIT-013 — storage/db.py WAL silently discards all writes — VERIFIED
- Severity: critical | Commit: cb06337
- Evidence: `_ensure_wal() PRAGMA journal_mode=WAL` → `unrecognized configuration parameter "journal_mode"` on every get_connection(), server logs "Experiment DB init failed" each boot, POST experiment → GET success but DuckDB empty (in-memory only). ModelRegistry bypasses storage/db (raw connect) so unaffected.
- Fix: remove _ensure_wal, read_only=True path for readers, single-writer, document storage/db in audit, restart-survival proof.
- Verified: clean startup log, 10 experiments + 3 models survive restart, 4 restart-survival tests added. Commit a0b7ad1 → later 188/188.

### AUDIT-014 — Fail-loud only on storage/db docstring, not callers — VERIFIED
- Severity: high | Evidence: experiments/engine _init_db/_persist/_load_all catch Exception log warning continue; scheduler/service same + ignore self._db_path; ml/registry except (ImportError,Exception): pass with zero logging. Job-level _run_job wrapper correct but never sees swallowed exception.
- Fix: ImportError→info/debug, real Exception→ERROR+raise, API returns 5xx, ml/registry adds logging, narrow catches only.
- Verified: 3 deliberately broken paths each raised + logged + 5xx via TestClient. Commits 7db327c/d646534. 184→188, ruff 0.

### AUDIT-015 — UI never visually verified — VERIFIED (bugs fixed, new ones introduced)
- Severity: high | Evidence: headless Chromium via Tailscale 100.109.22.68, all 11 routes: direct nav to /strategies → {"detail":"Not Found"} (no SPA fallback), broker "Disconnected" despite paper keys, LLM inbox 0 llm (filter bug), StrategyLab empty dropdown/no chart, DataExplorer no chart, execution ticket "KILL SWITCH OR NO BROKER" ambiguous, design bare (no tokens/charts/hierarchy).
- Fix: SPA fallback via catch-all, broker pills, LLM origin filter (llm+llm_fallback), StrategyLab schema form + equity curve, DataExplorer candlestick (lightweight-charts), tokens.css system, ErrorBoundary.
- Verified: 11 screenshots, ruff 188/188 +1 GPU skip.

### AUDIT-016 — UI Correction Pass follow-ups — VERIFIED (partial)
- Evidence: DataExplorer TypeError addCandlestickSeries is not a function (v5 removed it → chart.addSeries(CandlestickSeries)) crash takes whole React tree; enum leak OrderSide.BUY; buy red backwards; backtest 79.6s no progress; pairs 500 on empty symbols.
- Fix: chart.addSeries API, ErrorBoundary at root, .value serialization, color map, elapsed counter + diagnosis (walk-forward loop), 400 validation + frontend guard.
- Verified: /data no pageerror, buy green, progress (3s→18s), pairs 400.

### AUDIT-017 — Design tokens never loading — FIXED DIRECTLY (no architect)
- Severity: high | Commit: 19bb825 | Evidence: main.tsx imported ./index.css (Vite boilerplate, purple #aa3bff light) never App.css/tokens.css → every page unstyled light-mode, sidebar missing, colors invisible. Chart crash fix correct but invisible until styled.
- Fix: `frontend/src/main.tsx:3 import './App.css'` (App.css imports tokens.css), rebuild `npm run build` → dist, rsync to Jetson, restart infisical run --token ... --env=dev, fresh screenshots → dark theme, sidebar, buy green, candlestick with grid.
- Verified: CSS now --bg:#0b0d11 --accent:#2e9bff served, screenshots re-captured.

---

## Current open findings (requires next prompts)

### AUDIT-018 — 3 MCP integration tests failing on HEAD
Severity: high
Status: OPEN
Found by: Muse Spark verify 2026-08-11
Commit inspected: 6952c86 (HEAD, 07048f2..6952c86 includes Telegram interactive bot)
Evidence:
- `pytest -q` 2026-08-11 on macOS: `3 failed, 197 passed, 1 skipped` — all in `tests/integration/test_mcp_server.py:1`:
  - test_mcp_server_starts_and_lists_tools — McpError
  - test_mcp_read_tool_works — McpError
  - test_mcp_write_tool_works — McpError
- `ruff check .` clean.
- Context: architect rewrote MCP to FastMCP at e94825e/8ac83d1, then fixed shared OrderService at 4f154eb, but integration harness still fails. Previous Codex audit at ff30157 scope flagged fresh OrderService per platform_tool call → RiskGovernor reset; that pattern may remain in `cudaquant/platform_tools/registry.py` write tools.
Required fix:
- Run `pytest tests/integration/test_mcp_server.py -v` with real API_AUTH_TOKEN/Tailscale, capture full traceback, fix server start + list_tools + read/write tools to go through shared `_get_shared_order_service()` (not per-call). Ensure `mcp` dep in `pyproject.toml` extras installed in both venvs.
- Add platform_tools test coverage (currently 0% at last coverage).
Verification: `pytest -q` 0 failures, `pytest -m mcp` or integration suite green, ruff 0.

### AUDIT-019 — STATUS.md / PLAN.md stale (40+ commits behind)
Severity: medium
Status: OPEN
Found by: Muse Spark 2026-08-11
Commit inspected: 6952c86 vs STATUS.md:6 claiming 3ff2deb
Evidence: `git log --oneline HEAD` shows 6952c86..3ff2deb = ~40 commits (Telegram bot, LLM tools, platform_tools, chat, MCP, design, Invalid Date fix). `STATUS.md` still lists Telegram as UNCOMMITTED, crypto as working-tree. Jetson last verified at 0a44707 per STATUS.md:8.
Required fix: rewrite STATUS.md to HEAD, update PLAN.md M4 checkmarks, CHANGELOG_AGENT.md entry for 6952c86, BLOCKERS.md reconcile (systemd manual step, Telegram chat_id now set 6369764765, FMP/FINNHUB keys live, DUCKDB_PATH test isolation via conftest.py).
Verification: `git status` clean, docs `git log -1` matches STATUS.

### AUDIT-020 — Scheduler “Next run: Invalid Date” + remaining gaps — VERIFIED
Severity: medium | Status: VERIFIED | Commit: df9aa8e | Verified: 2026-08-11 Muse Spark
Evidence: Was null→"None"→Invalid Date. Fixed `Scheduler.tsx:25 iso?"—"`; `verify_cleanup.sh:1` now `ps aux | grep [u]vicorn.*cudaquant`; `model_routes.py:79` note; BLOCKERS.md WS documented. Local `pytest -q` 200/1 ruff 0, Welcome route exists.

### AUDIT-021 — Product not yet user-ready (holistic) — FIXED_PENDING_VERIFICATION (welcome done, P&L/docs/soak remain)
Severity: high | Status: FIXED_PENDING_VERIFICATION | Commit: df9aa8e
Evidence: Welcome wizard at `Welcome.tsx:1` (5 steps health→readiness→generate data→backtest→experiment, real API) addresses first-run gap; live-performance still stub but now labeled (model_routes note); unattended soak, docs, delete endpoints still open — see next prompt.
Required fix: operational polish + docs/soak (next architect prompt below).

---

## Verification log (continuity)
- 2026-08-10T06:06 Verified 0a44707 e2e via scripts/e2e_test.sh (health/readiness/system/strategies/backtest/dashboard/GPU dispatch/experiments) — last full Jetson e2e.
- 2026-08-11 Muse Spark: `pytest -q` 197/3/1, ruff 0, `git rev-parse HEAD` 6952c86, `git status` 1 untracked (claude_export_temp.md), STATUS stale, MCP 3 failures, UI main.tsx fix verified (dark tokens live).
- 2026-08-11 20:32 Muse Spark: `pytest -q` 200/1 skip ruff 0 after MCP FastMCP fix (555b9cb→dac8d7a). Repo STATUS reconciled.
- 2026-08-11 User-Ready Verified (commit df9aa8e): local checks — `frontend/src/pages/Welcome.tsx:1` 5 real API steps, `Scheduler.tsx:25` "—" fix, `scripts/verify_cleanup.sh:1` pgrep not port, `model_routes.py:79` live-performance note, BLOCKERS.md WS documented, `frontend/src/App.tsx:Route path="/welcome"`, 200/1 skip, SPA routes 200, report 179 unit + 8 GPU + 24 screenshots — no discrepancy found (179 vs 200 is unit-only vs full suite).

## Next verification discipline (for all future auditors)
- Never trust prose summaries — re-run `pytest -q`, `ruff check .`, `git status`, `curl http://100.109.22.68:8000/readiness`, headless browser load, and direct DuckDB reads.
- Pasted command output required, not paraphrase.
- UI: screenshots + pageerror checks, not “looks good” claims.
- Platform tools: prove shared-instance (invoke 3 times → one RiskGovernor counter).
- Persistence: POST → GET same process → kill/restart → GET again (both API + direct DB).
