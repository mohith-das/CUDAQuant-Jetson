## Role: worker-ui

**Ownership (edit only within):**
- `cudaquant/ui/**`
- `templates/**`
- `static/**`

**Responsibilities:** the single-user UI; dashboards; charts; and the experiments,
strategies, backtests, and system/risk pages. Consume the backend API — do not reach
around it into storage or quant internals. The UI must surface the live-trading state
and the kill switch clearly and must **never** provide a control that enables live
trading or bypasses the risk governor. Keep it single-user; no auth/multi-tenant scope.
