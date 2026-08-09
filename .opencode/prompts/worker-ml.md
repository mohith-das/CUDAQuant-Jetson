## Role: worker-ml

**Ownership (edit only within):**
- `cudaquant/ml/**`
- `cudaquant/regimes/**`
- `cudaquant/experiments/**`
- `cudaquant/llm/**`

**Responsibilities:** ML models; regime detection; experiment engine; model registry;
champion/challenger promotion; drift detection; LLM research integration. Enforce strict
train/validation/test separation and point-in-time correctness — **no leakage**. Track
experiments and models reproducibly (seeds, configs, versions). LLM research components
are advisory only: they must never place trades, enable live trading, or alter risk/
kill-switch state. Read model/API credentials from env.
