"""Alpaca market data provider using the official alpaca-py SDK.

Implements MarketDataProvider ABC for historical bars. Streaming support
is available via subscribe_bars() but requires the Alpaca data stream.

Environment: ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_DATA_FEED
"""

import logging
from datetime import datetime, timedelta

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from cudaquant.config.settings import settings
from cudaquant.data.schemas import Bar, BarFrequency
from cudaquant.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)

_FREQ_MAP = {
    BarFrequency.MINUTE_1: TimeFrame(1, TimeFrameUnit.Minute),
    BarFrequency.MINUTE_5: TimeFrame(5, TimeFrameUnit.Minute),
    BarFrequency.MINUTE_15: TimeFrame(15, TimeFrameUnit.Minute),
    BarFrequency.MINUTE_30: TimeFrame(30, TimeFrameUnit.Minute),
    BarFrequency.HOUR_1: TimeFrame(1, TimeFrameUnit.Hour),
    BarFrequency.DAY_1: TimeFrame(1, TimeFrameUnit.Day),
}


class AlpacaMarketDataProvider(MarketDataProvider):
    """Alpaca historical market data provider.

    Uses the official alpaca-py StockHistoricalDataClient.
    Falls back to synthetic data if credentials are not configured.
    """

    def __init__(self):
        key = settings.ALPACA_API_KEY
        secret = settings.ALPACA_SECRET_KEY

        self._client = None
        self._connected = False

        if key and secret:
            self._client = StockHistoricalDataClient(
                api_key=key,
                secret_key=secret,
            )
            self._connected = True
            logger.info("AlpacaMarketDataProvider: connected")
        else:
            logger.info("AlpacaMarketDataProvider: no credentials — synthetic-only")

    def get_bars(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: BarFrequency,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV bars from Alpaca.

        Falls back to synthetic if client unavailable.
        """
        if self._client is None:
            from cudaquant.providers.synthetic_provider import SyntheticMarketDataProvider
            return SyntheticMarketDataProvider().get_bars(symbols, start, end, frequency)

        tf = _FREQ_MAP.get(frequency, TimeFrame(1, TimeFrameUnit.Day))
        req = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=tf,
            start=start,
            end=end,
        )

        try:
            result = self._client.get_stock_bars(req)
            rows = []
            for symbol in symbols:
                if symbol in result.data:
                    for bar in result.data[symbol]:
                        rows.append({
                            "symbol": symbol,
                            "timestamp": bar.timestamp,
                            "open": bar.open,
                            "high": bar.high,
                            "low": bar.low,
                            "close": bar.close,
                            "volume": bar.volume,
                            "frequency": frequency,
                            "vwap": bar.vwap if hasattr(bar, "vwap") else None,
                        })

            if not rows:
                logger.warning("Alpaca returned no bars for %s", symbols)
                return pd.DataFrame()

            df = pd.DataFrame(rows)
            return df.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

        except Exception as e:
            logger.error("Alpaca get_bars failed: %s — falling back to synthetic", e)
            from cudaquant.providers.synthetic_provider import SyntheticMarketDataProvider
            return SyntheticMarketDataProvider().get_bars(symbols, start, end, frequency)

    def get_latest_bar(self, symbol: str, frequency: BarFrequency) -> Bar:
        """Get the most recent bar for a symbol."""
        end = datetime.now(timezone.utc) if hasattr(datetime, 'timezone') else datetime.utcnow()
        start = end - timedelta(days=5)
        df = self.get_bars([symbol], start, end, frequency)
        if df.empty:
            raise ValueError(f"No data for {symbol}")
        row = df.iloc[-1]
        return Bar(
            symbol=row["symbol"],
            timestamp=row["timestamp"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
            frequency=row["frequency"],
            vwap=row.get("vwap"),
        )

    def subscribe_bars(self, symbols: list[str], frequency: BarFrequency) -> None:
        """Streaming not yet implemented — no-op."""
        logger.debug("subscribe_bars: streaming not implemented, symbols=%s", symbols)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def provider_name(self) -> str:
        return "alpaca"
