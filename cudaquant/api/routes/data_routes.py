"""Data API routes — synthetic generation, symbol listing, bar fetching."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from cudaquant.api.auth import require_auth
from cudaquant.data.schemas import BarFrequency
from cudaquant.data.synthetic import SyntheticDataGenerator
from cudaquant.providers.alpaca_provider import AlpacaMarketDataProvider
from cudaquant.config.settings import settings

router = APIRouter(prefix="/api/data", tags=["data"], dependencies=[Depends(require_auth)])


@router.get("/symbols")
def list_symbols():
    """List available symbols. Returns Alpaca defaults if configured, else synthetic."""
    return {"symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "SPY", "QQQ"]}


@router.post("/generate")
def generate_synthetic(
    symbols: str = "AAPL",
    days: int = 5,
    frequency: str = "5m",
    seed: int = 42,
):
    """Generate synthetic bars and return as JSON."""
    freq = BarFrequency(frequency)
    gen = SyntheticDataGenerator(seed=seed)
    end = datetime.now(timezone.utc)
    start = end.replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    start = start - timedelta(days=days)

    df = gen.generate_bars(
        symbols=symbols.split(","),
        start=start,
        end=end,
        frequency=freq,
    )
    return df.to_dict(orient="records")


@router.get("/bars")
def get_bars(
    symbol: str = "AAPL",
    days: int = 5,
    frequency: str = "5m",
):
    """Fetch recent bars for charting."""
    freq = BarFrequency(frequency)
    end = datetime.now(timezone.utc)
    start = end.replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    start = start - timedelta(days=days)

    provider = AlpacaMarketDataProvider()
    df = provider.get_bars([symbol], start, end, freq)
    if df.empty:
        gen = SyntheticDataGenerator(seed=42)
        df = gen.generate_bars([symbol], start, end, freq)
    return df.to_dict(orient="records")
