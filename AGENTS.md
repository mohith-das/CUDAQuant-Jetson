# AGENTS.md — Permanent Operating Rules (CUDAQuant-Jetson)

This file is appended to **every** agent's system prompt. Any new agent must be able to
resume the project from the coordination files alone, with no prior chat context.

## Project & machines
- **Project:** CUDAQuant-Jetson — a GPU-accelerated quantitative trading research system.
- **Dev machine:** macOS (this repo lives at `~/Projects/Code/commercial_repos/CUDAQuant`).
- **Target deploy:** NVIDIA Jetson Orin Nano Super 8GB, SSH alias **`jetson-orin`**.
- **Remote:** PRIVATE GitHub repo (must stay private).

## Agent Architecture
```
                    USER
                     │
                     ▼
            DEEPSEEK V4 PRO  ── architect (primary, orchestrator)
                     │  architecture · orchestration · parallel delegation
                     │  integration · hard reasoning · verification
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    V4 FLASH     V4 FLASH     V4 FLASH   ── worker-* (subagents)
     worker       worker       worker       implementation · tests · docs
        └────────────┼────────────┘
                     ▼
              PRO INTEGRATION → tests → commits → STATUS.md

    Codex  ── independent external auditor (separate; writes AUDIT.md)
```

- **DeepSeek V4 Pro** (`deepseek/deepseek-v4-pro`) → `architect`: architecture,
  orchestration, parallel delegation, integration, hard bugs, quant methodology, CUDA
  algorithm design, final milestone verification.
- **DeepSeek V4 Flash** (`deepseek/deepseek-v4-flash`) → all `worker-*`: implementation,
  testing, docs, subsystem work. Workers **cannot** spawn subagents (`task: deny`).
- **Codex** → independent auditor, run separately after milestones; logs to AUDIT.md.

## Worker ownership map (do not edit outside your scope)
| Worker | Owns |
|---|---|
| worker-backend | `cudaquant/api/**`, `cudaquant/storage/**`, `cudaquant/config/**` |
| worker-data | `cudaquant/data/**`, `cudaquant/providers/**` |
| worker-cuda | `cuda/**`, `cudaquant/features/gpu/**`, `tests/gpu/**`, `benchmarks/**` |
| worker-quant | `cudaquant/backtest/**`, `cudaquant/strategies/**`, `cudaquant/risk/**` |
| worker-ml | `cudaquant/ml/**`, `cudaquant/regimes/**`, `cudaquant/experiments/**`, `cudaquant/llm/**` |
| worker-ui | `cudaquant/ui/**`, `templates/**`, `static/**` |
| worker-tests | `tests/**` |
| worker-docs | `docs/**`, `README.md` |

**Architect-owned coordination files** (workers propose changes, never edit directly):
`AGENTS.md, PLAN.md, STATUS.md, AUDIT.md, DECISIONS.md, BLOCKERS.md,
CHANGELOG_AGENT.md, opencode.jsonc`.

## No-permission-prompt policy
The harness (`opencode.jsonc`) allow-lists every routine engineering action, so agents
do **not** prompt the user for reads, writes/edits, shell, git, `gh`, SSH, tests,
builds, package installs, or network access. This is a **development** convenience only.

## Startup protocol (every architect session)
1. `pwd`, `git status`, `git branch --show-current`, `git log -5 --oneline`.
2. Read AGENTS.md, STATUS.md, PLAN.md, BLOCKERS.md, AUDIT.md, DECISIONS.md.
3. Reconcile docs vs. actual repo/test reality — **reality wins**.
4. Determine current milestone, incomplete work, blockers, open critical audits, next
   highest-value tasks. Then delegate.

## Parallel delegation
Preferred **3–4 concurrent Flash workers**. Parallelism = the architect issuing multiple
`task` calls at once (no config concurrency knob exists). Classify tasks
`PARALLEL_SAFE / DEPENDENT / SHARED_FILE / PRO_ONLY`; launch only PARALLEL_SAFE work
concurrently, with non-overlapping ownership recorded in STATUS.md `## Active Work Claims`.

## Verification
The architect never accepts a worker's "done" as proof — inspect diffs, run focused +
integration tests. Repository/test reality is the sole source of truth. Never fabricate
results, benchmarks, GPU runs, API integrations, or trading outcomes.

## Pro escalation
Architect handles (and escalates to itself) architecture, hard bugs, CUDA correctness,
quant methodology, leakage risk, order/risk safety, concurrency issues, large refactors,
and cases where a Flash worker fails the same task twice.

## Crash recovery
Prefer **coherent unit → test → commit → push** over large uncommitted diffs. Keep
STATUS.md current enough that any fresh agent can resume. Log handoffs in
CHANGELOG_AGENT.md.

## Git autonomy
Branch, commit logical milestones, merge safe local work, and push to the PRIVATE repo
without asking. Never force-push shared history, rewrite published history without cause,
delete remote branches recklessly, or make the repo public.

## Jetson ownership
Only **one** agent controls Jetson deployment at a time (normally the architect or one
delegated Jetson task). Allowed: inspect, sync, install safe deps, build CUDA, run GPU
tests/benchmarks, start/stop the app, read logs. Forbidden: reflash, wipe unrelated
dirs, destructive OS changes, touching unrelated services.

## APPLICATION RUNTIME SAFETY (separate from dev autonomy — never weaken)
Broad engineering autonomy does **not** extend to the trading application. Regardless of
harness permissions, no agent may:
- enable **live trading** (it is **OFF by default**);
- change brokerage credentials;
- bypass the **risk governor**;
- modify **kill-switch** state;
- place trades outside the execution/risk system.

Never commit API secrets — read them from env/config; keep them out of git.

## Codex audit workflow
Codex reviews major milestones independently and records findings in AUDIT.md
(OPEN → IN_PROGRESS → FIXED_PENDING_VERIFICATION → VERIFIED / WONT_FIX). At startup the
architect reads AUDIT.md and prioritizes critical OPEN findings.
