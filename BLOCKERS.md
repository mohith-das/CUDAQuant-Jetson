# BLOCKERS.md — Genuine External Blockers

> Only real, external blockers belong here (missing credentials, unreachable hardware,
> upstream outages). When blocked, record it, then **continue every unrelated task**.
> Remove entries when resolved.

## Open
- **None currently.**

## Resolved
- ~~PRIVATE GitHub repo did not exist / dir was not git-initialized~~ → resolved during
  harness bootstrap (2026-08-09): `git init` + private repo created + pushed.
- ~~Jetson SSH not accessible~~ → resolved (2026-08-09): corrected SSH config to `matt@matt.local`.
  Connection verified, environment documented in `docs/JETSON_ENVIRONMENT.md`.

## Reference — credentials & their state (do not paste secrets)
| Dependency | State | Needed for |
|---|---|---|
| DeepSeek API | ✅ authenticated in OpenCode | architect + workers |
| GitHub (`gh`, `mohith-das`) | ✅ authenticated, `repo` scope | push to PRIVATE remote |
| Jetson `jetson-orin` SSH | ✅ alias present (not yet contacted) | GPU build/test/deploy |
| Alpaca API keys | ⚠️ not configured (not yet needed) | live/paper market data (Milestone 3) |
