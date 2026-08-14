# DECISIONS.md — Architectural Decision Records

## ADR-0001 — DeepSeek V4 Pro Architect + V4 Flash Worker Pool
**Date:** 2026-08-09 · **Status:** Accepted

**Context:** CUDAQuant-Jetson must be built autonomously by OpenCode with high
throughput and reliable correctness on GPU/quant code.

**Decision:** One primary orchestrator, `architect`, on **DeepSeek V4 Pro**
(`deepseek/deepseek-v4-pro`); a pool of eight domain-specialized subagent workers on
**DeepSeek V4 Flash** (`deepseek/deepseek-v4-flash`). Pro does the expensive reasoning
(architecture, integration, hard bugs, quant/CUDA methodology, verification); Flash does
the bulk of implementation, tests, and docs. Pro launches 3–4 workers concurrently for
independent work.

**Rationale:** Concentrates costly frontier reasoning where correctness matters
(leakage, risk safety, CUDA parity) while parallelizing cheap, well-scoped
implementation. Explicit per-agent model pinning prevents workers from inheriting Pro.

## ADR-0002 — OpenCode 1.18.10 config generation (do not mix)
**Date:** 2026-08-09 · **Status:** Accepted

**Context:** Older docs suggested `permissions`/`shell`/`task` vs newer
`permission`/`bash`/`subagent` variants; the task warned against mixing generations.

**Decision:** Verified against the **installed** OpenCode **1.18.10** and the live schema
at `https://opencode.ai/config.json`. This repo uses the current generation:
- top-level & per-agent **`permission`** object with keys `read, list, glob, grep, edit,
  bash, task, external_directory, lsp, skill, webfetch, websearch, todowrite, question`;
- agents under **`agent`** (singular) with `mode` ∈ {primary, subagent}, `model`,
  `prompt` (supports relative `{file:...}` refs), `steps`, `permission`;
- custom commands under **`command`** with `template` (required), `description`, `agent`.
No `dangerouslySkipPermissions` / `yolo` / `max_workers` / `concurrency` key exists —
those were **not** invented. Installed version already exceeds the 1.14.24 floor, so **no
upgrade** was performed.

## ADR-0003 — Non-interactive permissions via config allow-list
**Date:** 2026-08-09 · **Status:** Accepted

**Decision:** Achieve the requested "YOLO / no routine prompts" via the top-level
`permission` block set to `allow` for every routine tool, rather than the `--auto` CLI
flag (which is transient and not committed). The committed config makes the behavior
reproducible for every future session. `doom_loop` is left at its default guard.

## ADR-0004 — Worker recursion depth limited to 1 (architect ▶ worker)
**Date:** 2026-08-09 · **Status:** Accepted

**Decision:** Every worker sets `permission.task = "deny"`, so a worker cannot spawn any
subagent — preventing uncontrolled recursive worker trees. The architect's `task`
permission allow-lists exactly the eight workers (`*: deny`), so it cannot invoke itself
or other primaries. Net topology depth: `architect → worker` only.

**Rationale:** OpenCode's `task` permission is the supported mechanism for this; it is
deterministic and needs no unsupported "depth" key.

## ADR-0006 — Jetson-specific torch wheel + single cupy package for CUDA 13.2
**Date:** 2026-08-09 · **Status:** Accepted

**Context:** Generic PyPI `torch` aarch64 wheel (2.13.0+cu130) emits a UserWarning
that SM 8.7 (Orin) is not in its compiled kernel list — it's silently relying on
PTX JIT, which is not a validated configuration. Additionally, two conflicting
cupy packages (`cupy-cuda11x` and `cupy-cuda12x`) were installed simultaneously,
which cupy's own docs say is undefined behavior.

**Decision:**
- Switch torch to the Jetson-Orin-Wheels community build
  (`torch-2.12.0-cp312-cp312-linux_aarch64.whl` from
  https://github.com/Shattered217/Jetson-Orin-Wheels/releases/tag/7.2.0),
  built specifically for JetPack 7.2.0 / CUDA 13.2 / cuDNN 9 / SM 8.7.
  Verified: no SM 8.7 warning, `torch.cuda.is_available()` returns True,
  real training step (forward+backward) works correctly. Pinned in
  pyproject.toml `gpu` extra with a comment explaining why it's not PyPI.
- Uninstall both cupy variants, install single `cupy-cuda13x>=14.1` (matches
  CUDA 13.2 exactly). Verified: `import cupy` produces no conflict warning.
- Generic `torch>=2.1` kept in pyproject.toml for non-Jetson environments.
  `cupy-cuda13x` conditioned on `platform_machine == 'aarch64'`; generic
  `cupy>=14.0` for other platforms.

**Rationale:** Running on a PTX-JIT torch build for production ML would be
irresponsible — numerical correctness is not guaranteed. The community wheel
is built for this exact hardware/JetPack/CUDA combo and has been verified
with a real training step. CuPy conflict resolved to a single matching package.

## ADR-0007 — Feature dispatch layer with empirically-measured thresholds
**Date:** 2026-08-09 · **Status:** Accepted

**Context:** Every real consumer (strategies, regimes) was using CPU features
directly (`cudaquant.features.engine`), bypassing the GPU kernels entirely.
Naively routing everything to GPU would make most operations slower due to
transfer/launch overhead on the small Jetson GPU.

**Decision:** Build `cudaquant/features/dispatch.py` with per-function size
thresholds measured empirically on the Jetson Orin (`benchmarks/measure_crossover.py`):
- rolling_min/max: GPU at n≥1,000 (CPU O(n·w) loop is pathologically slow)
- rolling_zscore: GPU at n≥20,000
- rolling_std/variance: GPU at n≥100,000
- rolling_mean/sum, returns: never GPU (CPU O(n) is always faster)
- Non-GPU features (RSI, ATR, VWAP, etc.): remain CPU-only
Dispatch checks: (1) settings.CUDA_ENABLED, (2) library actually loadable,
(3) array size above threshold. Stats are tracked for observability.
Consumers (`strategies/`, `regimes/`) now import from `cudaquant.features`
(the dispatch package) instead of `cudaquant.features.engine`.

## ADR-0008 — GPU logistic regression via torch rather than RAPIDS/cuML
**Date:** 2026-08-09 · **Status:** Accepted

**Context:** RAPIDS cuML 26.8.0 was installed on Jetson but fails to import
due to CUDA version mismatch (requires CUDA 12 `libnvrtc.so.12`; Jetson has
CUDA 13.2). No `cuml-cu13` package exists. See BLOCKERS.md for details.

**Decision:** Build `TSLogisticRegressionGPU` using torch CUDA (SGD, binary
cross-entropy, L2 regularization) behind the same fit/predict_proba/predict
interface as the CPU sklearn version. Factory function
`create_logistic_regression()` auto-selects GPU (torch) or CPU (sklearn)
based on config + CUDA availability. Verified: 99.3% prediction agreement,
92.3% prob correlation with CPU baseline.

RandomForest remains CPU-only (sklearn) — documented in BLOCKERS.md with
the specific investigation performed (RAPIDS CUDA 12 vs Jetson CUDA 13.2
incompatibility, no cuML-cu13 available).

## ADR-0009 — React+TypeScript+Vite frontend, built off-device, served as static files
**Date:** 2026-08-10 · **Status:** Accepted

**Context:** The UI must run entirely on the Jetson (no separate web server),
but the Jetson has no Node.js toolchain and installing one would add ~500MB
of packages to an already memory-constrained 8GB device.

**Decision:** Frontend lives in `frontend/` as a React+TypeScript+Vite project,
built on the dev machine (macOS) or CI, producing a static `dist/` bundle.
FastAPI mounts `frontend/dist/` via `StaticFiles` at `/` with SPA fallback
routing. The Jetson never needs Node — it only receives static HTML/JS/CSS.
`scripts/deploy_jetson.sh` builds the frontend as part of the deploy step.

**Rationale:** Keeps the Jetson as a pure Python+CUDA runtime. The build
artifact is ~450KB gzipped JS + 3.5KB CSS + an HTML shell — negligible
memory impact at runtime.

## ADR-0010 — lightweight-charts (TradingView) for financial charting
**Date:** 2026-08-10 · **Status:** Accepted

**Context:** The UI needs candlestick charts with overlays (indicators, trade
markers) and equity curves. Generic chart libraries (Recharts, Chart.js) lack
candlestick support or perform poorly with time-series financial data.

**Decision:** Use `lightweight-charts` v5 (TradingView's open-source charting
library). It provides native candlestick series, time-axis formatting,
built-in crosshair/tooltip, and is designed for financial data rendering at
scale. No other charting library was evaluated because lightweight-charts is
the de facto standard for embedded financial charting in web apps.

**Alternatives considered:** Recharts (no candlestick support), Chart.js
(financial plugin is community-maintained and lagging), custom Canvas (too
much bespoke code for this project's scope).

## ADR-0011 — Bearer token auth for LAN-exposed API
**Date:** 2026-08-10 · **Status:** Accepted

**Context:** The API can submit broker orders and engage/disengage a kill
switch. It must be exposed on the LAN (HOST=0.0.0.0) so the user can access
the UI from their Mac browser, but cannot be wide open.

**Decision:** 
- `API_AUTH_TOKEN` in settings/.env — a simple shared secret.
- Bearer token required on all `/api/*` and `/ws/*` routes.
- `/health` and `/readiness` remain unauthenticated (needed for basic monitoring).
- Fail-closed: if `HOST != 127.0.0.1` and `API_AUTH_TOKEN` is unset/placeholder,
  the app refuses to start with a clear error message.
- Token generated by `setup.sh` on first run and printed once.

**Rationale:** A full OAuth/OIDC flow is overkill for a single-user research
tool on a private LAN. The bearer token provides defense-in-depth — even if
the firewall is misconfigured, the API is not anonymously accessible. The
fail-closed startup check prevents the most dangerous misconfiguration (wide
open on LAN with no auth).

## ADR-0012 — APScheduler for in-process async scheduling
**Date:** 2026-08-10 · **Status:** Accepted

**Context:** Part 2 introduces scheduled jobs (ingest, retrain, evaluate,
llm_analyze). The scheduler must live in the same FastAPI process on the
Jetson (no separate infra), must integrate with the asyncio event loop, and
must persist its configuration across restarts.

**Decision:** Use **APScheduler** (`AsyncIOScheduler` + `IntervalTrigger`)
inside `cudaquant/scheduler/service.py`. Job cadences, enabled flags, run
history, and the auto-execute flag persist to DuckDB. The service exposes a
REST surface (via `scheduler_routes.py`) for toggling jobs and running them
immediately; the app wires real callbacks at startup.

**Alternatives considered:**
- **cron (system crontab):** rejected — separate process, no runtime
  toggling, no result history, awkward to co-locate with the API and its
  gates.
- **Celery / Celery Beat:** rejected — needs a broker (Redis/RabbitMQ) and
  worker processes; overkill and a memory/ops burden on an 8GB Jetson that
  runs a single FastAPI process.
- **Hand-rolled asyncio loop:** rejected — APScheduler provides interval
  triggers, job tracking, and cleanup for free; a hand-rolled loop is more
  code to get wrong.

**Consequences:** Scheduler runs in-process, so a crash of the API also
stops scheduling (acceptable for a research system). All jobs run in the
same asyncio loop — callbacks must be non-blocking or short enough not to
starve API responses.

## ADR-0013 — Four independent execution gates (config, RiskGovernor, KillSwitch, SCHEDULER_AUTO_EXECUTE)
**Date:** 2026-08-10 · **Status:** Accepted

**Context:** `OrderService.submit_order()` enforces three gates for every
order: (1) config (`TRADING_MODE`/`ENABLE_LIVE_TRADING`), (2)
`RiskGovernor.pre_trade_check()`, (3) `KillSwitch`. Those gates protect a
human/API-triggered submission path. Part 2 introduces the scheduler, which
creates a second, autonomous path to the same actions (retrain, evaluate,
and eventually execution) that runs **without a human in the loop** — a
single "paper/live config OK" state is not enough to authorize unattended
behavior.

**Decision:** Add a **4th independent gate** owned by the scheduler layer:
`SCHEDULER_AUTO_EXECUTE` (`SchedulerService.auto_execute_enabled`, persisted
in DuckDB, default **False**), checked via `can_auto_execute()`. Enabling it
requires an explicit confirm string on the API (`{"confirm": "ENABLE"}`).
The scheduler is additionally **structurally incapable of promotion** — no
`promote` method exists anywhere on the service, so no configuration of the
scheduler can ever promote a challenger; that remains a human UI action.

**Why a 4th gate is needed beyond OrderService's 3:** OrderService's gates
verify that a single, already-requested submission is safe at the moment of
submission. They say nothing about whether autonomous activity is permitted
in the first place. The 4th gate is the "autonomy consent" switch: even if
config, risk, and kill-switch all pass, the scheduler still must not act
unless auto-execution was explicitly, durably enabled for this session.
Separating the two keeps the manual path unchanged while making autonomous
behavior opt-in by construction. The gate is currently enforced by the
scheduler API and covered by tests; it is not yet consumed by any order path
because no autonomous order submission exists yet.

**Consequences:** Four gates must pass for any future autonomous order
placement. Default state is fully locked down; enabling requires an explicit
confirm and survives restart only if the operator re-enables it (persisted,
but surfaced prominently in the scheduler UI state).

## ADR-0014 — LLM as research agent, never trader
**Date:** 2026-08-10 · **Status:** Accepted

**Context:** The scheduler's `llm_analyze` job needs to produce research
value (performance analysis, experiment hypotheses) without ever gaining the
ability to place orders, change config, or promote models.

**Decision:** Keep `LLMResearchAgent` strictly advisory:
- Its outputs are **structured proposals** (`propose_experiment`) and text
  analysis (`analyze_performance`); it has no method that touches
  OrderService, RiskGovernor, KillSwitch, or ModelRegistry promotion.
- The scheduler auto-enqueues proposals to **ExperimentEngine** via
  `ExperimentEngine.propose(origin=ExperimentOrigin.LLM)` — the LLM produces
  only a hypothesis string and reasoning summary; execution of experiments is
  handled by the deterministic experiment runner.
- All validation is deterministic: no LLM output is ever executed, parsed
  into orders, or trusted as a safety decision. Without an API key the agent
  falls back to local deterministic defaults.

**Rationale:** The value of an LLM here is generating hypotheses faster than
a human, not making safety-critical decisions. Pinning the LLM to
proposal-only, with deterministic execution and validation downstream, keeps
any hallucinated or adversarial output inside the research queue where it can
only waste compute — never place trades or bypass gates.

**Consequences:** No future change may give the LLM direct access to order
submission or promotion. New LLM capabilities must go through
ExperimentEngine proposals and the existing gate stack (see ADR-0013).

## ADR-0015 — AlpacaCryptoMarketDataProvider via CryptoHistoricalDataClient
**Date:** 2026-08-10 · **Status:** Accepted (implementation in working tree, uncommitted)

**Context:** Crypto assets are quoted in pair format ("BTC/USD", "ETH/USD") and
behave differently from equities (24/7 trading, fractional base quantities,
different TIF defaults). Reusing the stock `AlpacaMarketDataProvider` for crypto
would force symbol-format hacks and conflate two data models.

**Decision:** Add a separate `AlpacaCryptoMarketDataProvider` in
`cudaquant/providers/alpaca_crypto_provider.py` that uses the alpaca-py
**`CryptoHistoricalDataClient`** / `CryptoBarsRequest` directly, keeping the stock
`AlpacaMarketDataProvider` (`StockHistoricalDataClient`) untouched. It implements
the same `MarketDataProvider` ABC, uses crypto-pair symbol format ("BTC/USD"), and
is registered alongside the stock provider. Broker-side, order TIF is selected per
symbol: `TimeInForce.GTC` when the symbol contains "/" (crypto), else
`TimeInForce.DAY` (equities).

**Rationale:** Clean separation — the two providers map to two distinct alpaca-py
clients with different request types and symbol conventions. Keeping them separate
avoids conditional branches in the stock provider and matches alpaca-py's own API
split. Distinct TIF defaults reflect that crypto trades 24/7 (DAY TIF would expire
unfilled overnight).

**Consequences:** Providers must be selected by asset class at call sites. The
crypto provider is implemented in the working tree but **not yet committed** — see
STATUS.md "Crypto support — working tree". Validation that crypto pair symbols
reach the right provider is pending.

## ADR-0016 — Fractional quantities (float qty) for crypto support
**Date:** 2026-08-10 · **Status:** Accepted (implementation in working tree, uncommitted)

**Context:** Crypto quantities are fractional (e.g. 0.0234 BTC), unlike whole-share
equities. The `Order`/`Fill`/`Position`/`Trade` schemas declared `qty: int`, which
rejected fractional crypto quantities at pydantic validation — this was previously
tracked as the "fractional qty" crypto blocker.

**Decision:** Change `qty` from `int` to `float` in the `Order`, `Fill`, and
`Position` schemas (and `size`/`volume` in `Trade`/`Bar`) so fractional crypto
quantities validate end-to-end. Integer quantities remain valid (float accepts
them), so the equities path is unaffected. RiskGovernor already treats qty as
float internally (`float(order.get("qty", 0.0))`).

**Rationale:** One schema type that admits both whole-share and fractional orders is
simpler than a discriminated union or a separate crypto order type; float qty is a
superset of int qty. The earlier blocker test (`test_order_service_with_fractional_qty`)
asserted the old int-schema rejection and is now **stale/failing** until updated to
assert acceptance instead.

**Consequences:** The schema change is in the working tree, **not yet committed**.
The stale fractional-qty test must be updated (it currently fails) and the
int→float migration re-verified (float32 rounding on very small fractions is a
known numeric consideration). See STATUS.md for the current working-tree state.

## ADR-0017 — Telegram alerting (out-of-band notifications)
**Date:** 2026-08-10 · **Status:** Accepted (implementation in working tree, uncommitted)

**Context:** Critical events (kill-switch trips, scheduler job failures, models
ready for human review) are currently only visible in API responses and local
logs. On the headless Jetson, nobody sees those logs until they SSH in. The
operator wants cheap, out-of-band notification of the handful of events that
matter, without adding infrastructure.

**Decision:** Add a minimal `cudaquant/alerts/` package with a `TelegramAlerter`
that posts to the Telegram Bot API over `httpx` (already a dependency). Configured
by two new settings fields, `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (both
default `None`). It is wired at exactly three trigger points:
- kill-switch trip (`engage_kill_switch`)
- scheduler job exception (`_run_job` except block)
- challenger ready for review (`promote_to_challenger`, success only)

**Graceful degradation is a hard requirement:** if either credential is unset —
the default state — `send()` returns `False` without any network call, and no
call site wraps existing logic in new try/except. Non-200 responses and network
exceptions also return `False` (logged at WARNING). Alerting can never raise, so
it cannot break order/risk/kill-switch paths. Message text is HTML-escaped before
posting under `parse_mode=HTML` so dynamic content cannot fail the request.

**Alternatives considered:**
- **SMTP/email:** rejected — SMTP creds and an SMTP server are heavier to set up
  than a bot token, and email latency/threading is worse for ops alerts.
- **Self-hosted push (ntfy/Apprise):** viable, but adds a service to run; Telegram
  requires zero self-hosted infra and is already on the operator's phone.
- **Webhook to a generic endpoint:** no receiver exists; Telegram is the receiver.

**Consequences:** Alerting is best-effort and silent by default — do not treat a
`send()` result as a delivery guarantee (Telegram "sendMessage" 200 means accepted
by the API, not read). New alert call sites should append the fire-and-forget call
at the end of an existing path and keep messages factual (what happened + UTC
timestamp). Credentials remain env-only; never commit a real token/chat id.
Implementation lives in the working tree, **not yet committed** — see STATUS.md.

## ADR-0018 — Systemic audit of stateful class construction patterns
**Date:** 2026-08-10 · **Status:** Accepted

**Context:** Three correction passes identified the same root-cause bug: a
stateful class (ExperimentEngine, ModelRegistry, LLMResearchAgent) was
constructed fresh per call instead of shared, so accumulated state (budget
counters, cached DB loads) never persisted across calls. A full-tree audit
was required to find any remaining instances.

**Decision:** Audit completed across 34 stateful classes in cudaquant/.
Findings:
- **Already shared** (via get_shared_* or module-level singleton):
  ExperimentEngine, ModelRegistry, LLMResearchAgent, OrderService,
  SchedulerService (one instance in app.py lifespan).
- **Scoped correctly** (owned by a shared singleton, not constructed
  independently): RiskGovernor, KillSwitch, AlpacaBroker — all created
  inside OrderService.__init__.
- **Stateless / safe as-is** (per-call construction doesn't lose state):
  AlpacaMarketDataProvider (API client, no cross-call state),
  TelegramAlerter (reads config, sends HTTP, no accumulated state),
  AlpacaCryptoMarketDataProvider, SyntheticMarketDataProvider,
  BraveSearchTool/TavilySearchTool/FirecrawlTool (all stateless API
  clients), FMPProvider, FinnhubProvider, SearchCache (optional, used
  with explicit db_path).
- **Not applicable** (constructed per-backtest or per-request intentionally):
  DeterministicBacktester, Strategies, WalkForwardValidator,
  SyntheticDataGenerator, RegimeDetector, TSLogisticRegression,
  TSRandomForest, BatchedExperimentRunner.

No other instances of the fresh-construction-per-call bug found.

## ADR-0019 — Switch Jetson torch wheel to self-built native SM 8.7 source
**Date:** 2026-08-14 · **Status:** Accepted

**Context:** ADR-0006 pinned torch to the Jetson-Orin-Wheels community build
(torch-2.12.0, github.com/Shattered217/Jetson-Orin-Wheels) as a native SM 8.7
source, since PyPI's generic aarch64 wheel lacks SM 8.7 kernels and falls
back to PTX JIT (confirmed elsewhere to cost 10s+ per new tensor shape the
first time it's seen). That wheel is a third party's prebuilt binary with no
build script attached - reproducibility and provenance depend entirely on
that repo staying up.

**Decision:** Switch to a self-built native SM 8.7 wheel (torch 2.13.0),
built from PyTorch's own source via `build_pytorch.sh` in
github.com/mohith-das/jetson-jp7.2-pytorch-sm87, targeting this exact
JetPack 7.2 / L4T r39.2 / CUDA 13.2 / Python 3.12 environment. Verified with
the same bar as ADR-0006 - a real forward+backward+optimizer step, gradients
finite - plus `torch.cuda.get_arch_list() == ["sm_87"]`. Also now the single
torch source shared across glass_box and llm_distillery, which were still on
the broken generic PyPI wheel.

**Rationale:** Same correctness requirement as ADR-0006 (no PTX JIT for
production ML), but with a reproducible build script under our own control
instead of trusting an unrelated third party's binary indefinitely, and one
consistent torch source across every Jetson project instead of three
different ones (PyPI, Shattered217, and this) as of a day ago.
