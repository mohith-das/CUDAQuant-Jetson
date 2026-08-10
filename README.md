# CUDAQuant-Jetson

**GPU-accelerated quantitative trading research platform for NVIDIA Jetson Orin Nano.**

Built autonomously by OpenCode (DeepSeek V4 Pro architect + V4 Flash worker pool).

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

NVIDIA Jetson Orin Nano Super 8GB | JetPack 7.2 | CUDA 13.2

| Function | CPU (ms) | GPU (ms) | Speedup |
|---|---:|---:|---:|
| rolling_zscore | 6.04 | 1.79 | **3.4x** |
| rolling_std | 3.75 | 1.68 | **2.2x** |
| rolling_mean | 1.33 | 1.61 | 0.8x |
| simple_returns | 0.56 | 1.73 | 0.3x |

_n=100,000, window=20. Crossover point ~50k elements._

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
95 passed in 0.76s
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

- **Private:** `git@github.com:mohith-das/CUDAQuant-Jetson.git`
- **No secrets committed** — `.env`, API keys, and credentials excluded via `.gitignore`
- **Large data excluded** — Parquet/DuckDB files in `/data/` not tracked
