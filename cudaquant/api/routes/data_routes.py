"""Data API routes — synthetic generation, symbol listing, bar fetching, search, symbol info."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from cudaquant.api.auth import require_auth
from cudaquant.data.schemas import BarFrequency
from cudaquant.data.synthetic import SyntheticDataGenerator
from cudaquant.providers.alpaca_provider import AlpacaMarketDataProvider
from cudaquant.providers.finnhub_provider import FinnhubProvider
from cudaquant.providers.fmp_provider import FMPProvider

logger = logging.getLogger(__name__)

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


def _get_search_provider():
    """Return SearchProvider, or a clear 503 while the search service is unavailable."""
    try:
        from cudaquant.providers.search_provider import SearchProvider
    except ImportError as e:
        raise HTTPException(503, f"Search service unavailable: {e}") from e
    return SearchProvider()


@router.get("/search")
def search_symbols(q: str | None = None, limit: int = 10):
    """Search instruments by symbol or name via the search provider."""
    if not q or not q.strip():
        raise HTTPException(400, "q query parameter is required")
    limit = max(1, min(limit, 50))
    try:
        results = _get_search_provider().search(q.strip(), limit=limit)
    except HTTPException:
        raise
    except Exception as e:  # provider failure degrades to empty results
        logger.warning("search failed for q=%r: %s", q, e)
        results = []
    if isinstance(results, dict):
        results = results.get("results") or []
    normalized = []
    for r in results or []:
        if not isinstance(r, dict):
            continue
        normalized.append(
            {
                "symbol": r.get("symbol", ""),
                "name": r.get("name", ""),
                "exchange": r.get("exchange", ""),
                "type": r.get("type", ""),
            }
        )
    return {"results": normalized}


@router.get("/{symbol}/info")
def get_symbol_info(symbol: str):
    """Compose quote + profile + news for a symbol; each degrades to null/empty."""
    symbol = symbol.strip().upper()

    quote = None
    try:
        raw = _get_search_provider().get_quote(symbol)
        if isinstance(raw, dict) and raw:
            quote = dict(raw)
            quote.setdefault("price", None)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("quote failed for %s: %s", symbol, e)

    profile: dict = {}
    try:
        raw = FMPProvider().get_profile(symbol)
        profile = raw if isinstance(raw, dict) else {}
    except Exception as e:
        logger.warning("profile failed for %s: %s", symbol, e)

    news: list[dict] = []
    try:
        raw = FinnhubProvider().get_company_news(symbol)
        news = raw if isinstance(raw, list) else []
    except Exception as e:
        logger.warning("news failed for %s: %s", symbol, e)

    return {"symbol": symbol, "quote": quote, "profile": profile, "news": news}
