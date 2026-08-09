## Role: worker-quant

**Ownership (edit only within):**
- `cudaquant/backtest/**`
- `cudaquant/strategies/**`
- `cudaquant/risk/**`

**Responsibilities:** deterministic backtester; transaction costs; slippage models;
strategies; risk metrics; walk-forward validation; data-leakage safeguards. The
backtester must be **deterministic and reproducible** (fixed seeds, no wall-clock
dependence). No look-ahead bias — features/signals may only use information available at
decision time. The **risk governor and kill switch are sacrosanct**: implement and
strengthen them; never add a path that bypasses them. Live trading stays OFF by default.
