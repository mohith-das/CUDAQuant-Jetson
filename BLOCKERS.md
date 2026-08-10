# BLOCKERS.md — Genuine External Blockers

> Only real, external blockers belong here (missing credentials, unreachable hardware,
> upstream outages). When blocked, record it, then **continue every unrelated task**.
> Remove entries when resolved.

## Open
- **RAPIDS cuML RandomForest GPU path blocked** — cuML 26.8.0 (installed via pip) requires CUDA 12 runtime libraries (`libnvrtc.so.12`) but Jetson Orin runs CUDA 13.2. Attempted: installed `cuml-cu12 26.8.0` via pip, verified libraries exist under `site-packages/libcuml/lib64/` and `site-packages/libcuvs/lib64/`, set `LD_LIBRARY_PATH` to include both, but import fails with `ImportError: libnvrtc.so.12: cannot open shared object file`. The system provides `libnvrtc.so` (CUDA 13) only — no CUDA 12 compatibility. No `cuml-cu13` package exists yet on PyPI (checked 2026-08-09). **Impact:** RandomForest remains CPU-only (sklearn). Logistic regression has a working GPU path via torch (Jetson-Orin-Wheels build for CUDA 13.2/SM 8.7).

## Known limitations (not external blockers — tracked for completeness)
These are intentional defaults or incomplete work, not unavailable external
dependencies. Listed here per the Part 2 handoff so nobody mistakes them for
"done".
- **Live trading is OFF by default** — `ENABLE_LIVE_TRADING=False` everywhere;
  the app runs in `paper`/synthetic mode unless explicitly enabled. Scheduler
  auto-execute (`SCHEDULER_AUTO_EXECUTE`) is also OFF by default (ADR-0013).
- **LLM_API_KEY is effectively unset (documented state, not a blocker)** — the
  `.env` value is a placeholder, so `LLMResearchAgent` runs in local deterministic
  fallback mode (no provider configured). The system is fully functional without
  it; the LLM path simply produces default proposals/analyses.
- **Search tool wrappers not built** — `BRAVE_SEARCH_API_KEY`, `TAVILY_API_KEY`,
  `FIRECRAWL_API_KEY` settings fields exist (added in Correction Pass 3) but no
  Brave/Tavily/Firecrawl client code exists yet. Settings fields are forward
  declarations so pydantic `extra=forbidden` does not reject `.env` values.
- **Telegram alerting not configured (documented state, not a blocker)** — the
  `TelegramAlerter` (ADR-0017) reads `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`,
  which are unset by default; all alert call sites silently no-op until a real bot
  token + chat id are provided. No credentials exist to paste here.
- **Crypto support uncommitted / in-flight** — crypto provider, fractional qty,
  and GTC TIF exist only in the working tree (see STATUS.md); the fractional-qty
  test currently fails there pending a stale-assertion update.
- **Local `.env` drift (this Mac)** — `.env` contains `FMP_API_KEY` and
  `FINNHUB_API_KEY`, which are not Settings model fields (pydantic
  `extra=forbidden`), so `Settings()` raises and `pytest` fails at collection from
  the repo root. Working tree adds `extra="ignore"`; until committed, run tests
  with a clean env or remove those keys from `.env`.
- **live-performance endpoint is a stand-in** — `GET /api/models/{id}/live-performance`
  returns a filled-order count from OrderService plus stored backtest metrics;
  it is not realized P&L tracking yet.
- **WebSocket auth not enforced at connect time** — auth uses the query
  parameter / first message; not a full handshake check.

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
| Jetson `jetson-orin` SSH | ✅ alias present, verified working | GPU build/test/deploy |
| Alpaca API keys | ✅ configured in .env on both machines | live/paper market data + broker |
| Telegram bot token + chat id | ⬜ unset (optional) | out-of-band alerting (ADR-0017); alerts silently skip until provided |
