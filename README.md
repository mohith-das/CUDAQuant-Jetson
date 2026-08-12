# CUDAQuant-Jetson

**GPU-accelerated quantitative trading research platform for NVIDIA Jetson Orin Nano.**

## Architecture

```
Market Data → Parquet/DuckDB → CPU Features / CUDA GPU Kernels
                                    ↓
                          Deterministic Backtester
                                    ↓
              Strategies ← → ML Models → Model Registry
                                    ↓
                          Walk-Forward Validation
                                    ↓
                    Champion/Challenger Management
                                    ↓
                           Risk Governor
                                    ↓
                     Paper Execution (live OFF)
                                    ↓
                Trade Outcomes → Drift → LLM Research Agent
                                    ↓
                          Experiment Engine → New Experiments
```

## Features

### Data & Providers
- Pydantic v2 schemas (Bar, Order, Fill, Position, Account)
- Synthetic market data generator with 7 scenarios (trend, reversion, volatility spike, gap, missing data, flat, regime change)
- Provider abstractions: MarketDataProvider, Broker, NewsProvider, LLMProvider
- DuckDB + Parquet storage layer

### Feature Engineering
- **22 CPU functions:** returns, rolling mean/variance/std/min/max/zscore, RSI, ATR, VWAP, momentum, beta, correlation, relative volume, realized volatility, overnight gap, distance from high/low, time-of-day encoding
- **9 GPU kernels** (CUDA C++, compiled on Jetson): rolling stats, returns, z-score
- Graceful CPU fallback when GPU unavailable

### Backtesting
- Deterministic walk-forward engine with seeded RNG
- Transaction cost modeling: commission, slippage, spread, latency
- 13 metrics: Sharpe, Sortino, max drawdown, win rate, profit factor, expectancy, CAGR, turnover, etc.
- Strict no-look-ahead: chronological signal computation
- Walk-forward validation with expanding/rolling windows, purge/embargo gaps
- Leakage detection: lookahead check, target leakage, future normalization

### Strategies
- IntradayMomentum: breakout signals from rolling high/low
- MeanReversion: z-score based entry/exit
- PairsRelativeValue: spread trading with log-price ratio
- BuyAndHold baseline

### ML
- Time-series-aware models (no shuffling): logistic regression, random forest
- Model registry: candidate → challenger → champion → retired lifecycle
- DuckDB persistence for model lineage and metrics

### Regime Detection
- 4 market regimes: trending/ranging × high/low volatility
- Strategy performance attribution by regime

### Experiment Engine
- Full lifecycle: proposed → queued → running → completed
- Grid search, random search, evolutionary mutation
- Configurable budgets (concurrent, daily, weekend limits)

### LLM Research Agent
- Advisory only — never controls trading
- Structured experiment proposals (Pydantic)
- Works fully without API key (local rule-based analysis)
- USD/token/call budgeting

### Risk Management
- Centralized RiskGovernor (fail-closed on any unknown state)
- Position limits, exposure limits, daily loss/trade caps
- File-based KillSwitch with cross-process safety
- Live trading disabled by default (requires multiple explicit gates)

## Jetson Benchmarks

NVIDIA Jetson Orin Nano Super 8GB | JetPack 7.2 | CUDA 13.2 | torch 2.12.0

### Feature computation — dispatch layer

Features auto-route to GPU or CPU based on empirically-measured thresholds:

| Function | GPU threshold | Why |
|---|---|---|
| rolling_min, rolling_max | n ≥ 1,000 | CPU O(n·w) loop is pathologically slow |
| rolling_zscore | n ≥ 20,000 | GPU wins at larger sizes |
| rolling_std, rolling_variance | n ≥ 100,000 | GPU wins at very large sizes |
| rolling_mean, rolling_sum, returns | never GPU | CPU O(n) is always faster |

Batch feature computation (7 windows, n=5,000): **4.2x GPU speedup**
(rolling_min/max routed to GPU per thresholds above).

### ML training — logistic regression

| Metric | GPU (torch CUDA) | CPU (sklearn) |
|---|---|---|
| Training time (n=5k) | ~900 ms | ~1,600 ms |
| Prediction agreement | 99.3% | — |
| Probability correlation | 0.92 | — |
| Accuracy | 98.5% | 98.5% |

GPU and CPU paths converge to the same solution. See
`benchmarks/ml_gpu_parity.py` for reproduction.

### Batched experiment engine

Grid search profiling (12 combinations, n=200 bars):
- Feature computation: <0.1% of total runtime
- Backtester walk-forward loop: >99% of total runtime
- Batching features has negligible impact — backtester is the bottleneck

Full benchmarks with reproduction commands: `docs/CUDA_BENCHMARKS.md`.

## Quick Start

```bash
# Setup (creates venv, installs deps, builds CUDA on Jetson)
./setup.sh

# Run tests
python -m pytest tests/unit/ -v

# Start server
./start.sh
# → http://127.0.0.1:8000/health

# Stop server
./stop.sh
```

## Test Results

```
179 passed in 1.19s
```

All tests pass on macOS (CPU). GPU tests pass on Jetson with documented float32 precision limits.

## Deployment

```bash
# Deploy to Jetson Orin
./scripts/deploy_jetson.sh

# Or manually:
rsync -avz ./ matt@matt.local:~/cudaquant/
ssh matt@matt.local "cd ~/cudaquant && bash setup.sh && bash start.sh"
```

## Environment

Copy `.env.example` to `.env` and configure:

```bash
TRADING_MODE=paper           # paper | live
ENABLE_LIVE_TRADING=no       # requires "I_UNDERSTAND_LIVE_TRADING_RISK"
ALPACA_API_KEY=              # optional — synthetic mode works without
ALPACA_SECRET_KEY=           # optional
LLM_API_KEY=                 # optional — LLM agent falls back to local analysis
```

## Safety

- **Live trading is OFF by default.** Requires `TRADING_MODE=live` AND `ENABLE_LIVE_TRADING=I_UNDERSTAND_LIVE_TRADING_RISK`.
- Kill switch blocks all orders when engaged.
- Risk governor fails closed on any unknown state.
- LLM is advisory only — cannot place orders, modify credentials, or bypass risk controls.
- Paper/synthetic mode works fully without external API keys.

## Known Limitations

- Float32 GPU precision: std/variance match within 5e-2 (documented)
- GPU overhead dominates for n < ~50k
- Alpaca/LLM providers require API keys (all core functionality works without)
- UI not yet built (coming in next milestone)
- No live trading integration tested

## Repository

- `git@github.com:mohith-das/CUDAQuant-Jetson.git`
- API keys and credentials are excluded via `.gitignore` and never committed
- Parquet/DuckDB data files in `/data/` are not tracked
