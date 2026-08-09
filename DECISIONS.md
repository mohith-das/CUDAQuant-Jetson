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

## ADR-0005 — Application safety kept separate from dev autonomy
**Date:** 2026-08-09 · **Status:** Accepted

**Decision:** Broad OpenCode engineering permissions do **not** touch the trading
application's runtime safeguards. Live trading OFF by default; risk governor and kill
switch are never bypassed; secrets never committed. Enforced in app design + AGENTS.md,
not via harness permission prompts.
