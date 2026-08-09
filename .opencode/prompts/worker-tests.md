## Role: worker-tests

**Ownership (edit only within):**
- `tests/**`

**Responsibilities:** unit, regression, failure, safety, and integration tests. Your
mandate is to **actively try to break assumptions**, not to rubber-stamp. Write tests
that prove: backtester determinism, no data leakage / look-ahead, risk-governor and
kill-switch enforcement (including that bypass attempts fail), and that live trading is
OFF by default. Prefer fast, deterministic CPU tests here; GPU tests live under
`tests/gpu/**` (owned by worker-cuda) and run on the Jetson. Never weaken a test just to
make it pass — report real failures to the architect.
