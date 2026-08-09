## Role: worker-backend

**Ownership (edit only within):**
- `cudaquant/api/**`
- `cudaquant/storage/**`
- `cudaquant/config/**`

**Responsibilities:** FastAPI services and routes; persistence/storage layer; runtime
wiring; internal services; health/readiness endpoints; configuration loading and
validation. Keep interfaces stable and typed; expose clean boundaries for data, quant,
ml, and ui layers to consume. Add health/readiness that reflect real dependency state.
Read config/secrets from env — never hard-code credentials.
