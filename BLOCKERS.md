# BLOCKERS.md — Genuine External Blockers

> Only real, external blockers belong here (missing credentials, unreachable hardware,
> upstream outages). When blocked, record it, then **continue every unrelated task**.
> Remove entries when resolved.

## Open
- **RAPIDS cuML RandomForest GPU path blocked** — cuML 26.8.0 (installed via pip) requires CUDA 12 runtime libraries (`libnvrtc.so.12`) but Jetson Orin runs CUDA 13.2. Attempted: installed `cuml-cu12 26.8.0` via pip, verified libraries exist under `site-packages/libcuml/lib64/` and `site-packages/libcuvs/lib64/`, set `LD_LIBRARY_PATH` to include both, but import fails with `ImportError: libnvrtc.so.12: cannot open shared object file`. The system provides `libnvrtc.so` (CUDA 13) only — no CUDA 12 compatibility. No `cuml-cu13` package exists yet on PyPI (checked 2026-08-09). **Impact:** RandomForest remains CPU-only (sklearn). Logistic regression has a working GPU path via torch (Jetson-Orin-Wheels build for CUDA 13.2/SM 8.7).

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
