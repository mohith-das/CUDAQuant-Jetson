## Role: worker-data

**Ownership (edit only within):**
- `cudaquant/data/**`
- `cudaquant/providers/**`

**Responsibilities:** synthetic data generation; Alpaca provider integration; data
schemas; Parquet + DuckDB storage/access; streaming and ingestion; data-quality checks.
Enforce schema/type correctness and timestamp integrity. Guard against look-ahead and
survivorship issues at the data layer. Alpaca lives in **paper/read** context by
default; never wire live-trading order flow here. Read API keys from env only.
