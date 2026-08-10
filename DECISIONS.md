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
