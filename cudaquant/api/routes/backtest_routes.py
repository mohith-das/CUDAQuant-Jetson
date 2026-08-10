"""Backtest API routes — run and list backtests with persistence."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from cudaquant.api.auth import require_auth
from cudaquant.backtest.engine import DeterministicBacktester
from cudaquant.data.schemas import BarFrequency
from cudaquant.data.synthetic import SyntheticDataGenerator
from cudaquant.strategies.implementations import (
    IntradayMomentum,
    MeanReversion,
)

router = APIRouter(prefix="/api/backtests", tags=["backtests"], dependencies=[Depends(require_auth)])

# In-memory store (backed by DuckDB in production via experiments table)
_backtest_results: dict[str, dict] = {}


# Build actual registry from the strategies module
STRATEGY_REGISTRY = {
    "intraday_momentum": IntradayMomentum,
    "mean_reversion": MeanReversion,
}
try:
    from cudaquant.strategies.implementations import PairsRelativeValue
    STRATEGY_REGISTRY["pairs_relative_value"] = PairsRelativeValue
except ImportError:
    pass


@router.post("/run")
def run_backtest(payload: dict):
    """Run a single backtest and return results.

    Expected payload:
    {
        "strategy": "intraday_momentum",
        "params": {"lookback": 20},
        "symbols": ["AAPL"],
        "days": 30,
        "frequency": "5m",
        "capital": 100000
    }
    """
    strat_name = payload.get("strategy", "intraday_momentum")
    params = payload.get("params", {})
    symbols = payload.get("symbols", ["AAPL"])
    days = payload.get("days", 30)
    freq = BarFrequency(payload.get("frequency", "5m"))
    capital = payload.get("capital", 100_000)

    cls = STRATEGY_REGISTRY.get(strat_name)
    if cls is None:
        raise HTTPException(400, f"Unknown strategy: {strat_name}")

    # Validate required string params for strategies that need them
    if strat_name == "pairs_relative_value":
        for req in ("symbol_a", "symbol_b"):
            val = params.get(req, "").strip() if isinstance(params.get(req), str) else ""
            if not val:
                raise HTTPException(400, f"'{req}' is required for pairs_relative_value strategy")

    try:
        strategy = cls(**params)
    except TypeError as e:
        raise HTTPException(400, f"Invalid parameters: {e}") from e

    gen = SyntheticDataGenerator(seed=42)
    end = datetime.now(timezone.utc)
    from datetime import timedelta
    start = end.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)

    df = gen.generate_bars(symbols, start, end, freq)
    if df.empty:
        raise HTTPException(400, "No data generated")

    bt = DeterministicBacktester(initial_capital=capital, seed=42)
    result = bt.run(data=df, signal_fn=strategy.generate_signals)

    bt_id = str(uuid.uuid4())[:8]
    record = {
        "id": bt_id,
        "strategy": strat_name,
        "params": params,
        "symbols": symbols,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metrics": result.get("metrics", {}),
        "trades": result.get("trades", [])[:20],  # limit for response size
        "trade_count": len(result.get("trades", [])),
        "equity_curve": result.get("equity_curve", []),
    }
    _backtest_results[bt_id] = record
    return record


@router.get("/")
def list_backtests(limit: int = 20):
    """List recent backtest runs."""
    items = list(_backtest_results.values())
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]


@router.get("/{bt_id}")
def get_backtest(bt_id: str):
    """Get a specific backtest result."""
    if bt_id not in _backtest_results:
        raise HTTPException(404, "Backtest not found")
    return _backtest_results[bt_id]
