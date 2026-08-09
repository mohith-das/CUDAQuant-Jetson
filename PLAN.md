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

## Milestone 1 — Project scaffold (next; build with OpenCode, not Claude Code)
- [ ] Python project scaffold (`cudaquant/` package, `pyproject.toml`/deps, `tests/`)
- [ ] Config system + `.env.example` (secrets from env only)
- [ ] FastAPI app shell with health/readiness (worker-backend)
- [ ] Data schemas + synthetic data generator (worker-data)
- [ ] Deterministic CPU backtester skeleton + determinism test (worker-quant, worker-tests)
- [ ] Risk governor + kill switch interfaces, live-trading OFF by default (worker-quant)
- [ ] CI-style local test target (`pytest`) green

## Milestone 2 — GPU acceleration
- [ ] CUDA build setup for Jetson Orin (worker-cuda)
- [ ] First GPU feature kernel + CPU-reference parity test (worker-cuda, worker-tests)
- [ ] GPU backtester path aligned to CPU semantics
- [ ] Jetson build + GPU tests + benchmarks run on `jetson-orin`

## Milestone 3 — Data providers & ML
- [ ] Alpaca provider (paper/read) + Parquet/DuckDB storage (worker-data)
- [ ] Strategies + transaction-cost/slippage models + walk-forward (worker-quant)
- [ ] ML/regime/experiment engine + model registry + drift (worker-ml)
- [ ] LLM research integration (advisory only) (worker-ml)

## Milestone 4 — UI, deployment, docs
- [ ] Single-user UI dashboards + system/risk pages (worker-ui)
- [ ] Jetson deployment/runbook (worker-docs) + benchmark presentation
- [ ] README + architecture + deployment docs (worker-docs)
- [ ] First independent Codex audit pass (see AUDIT.md)

_The next OpenCode session owns execution from Milestone 1 onward._
