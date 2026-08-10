"""Synthetic market data provider for testing and development."""

from datetime import datetime

import pandas as pd

from cudaquant.data.schemas import Bar, BarFrequency
from cudaquant.data.synthetic import SyntheticDataGenerator
from cudaquant.providers.base import MarketDataProvider


class SyntheticMarketDataProvider(MarketDataProvider):
    """In-memory synthetic market data provider using SyntheticDataGenerator.

    No API keys or network required. Deterministic by default.
    """

    def __init__(self, seed: int = 42):
        self._generator = SyntheticDataGenerator(seed=seed)
        self._subscribed: dict[BarFrequency, list[str]] = {}

    def get_bars(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: BarFrequency,
    ) -> pd.DataFrame:
        return self._generator.generate_bars(
            symbols=symbols,
            start=start,
            end=end,
            frequency=frequency,
            seed=42,
        )

    def get_latest_bar(self, symbol: str, frequency: BarFrequency) -> Bar:
        """Return the most recent bar for a symbol (generates last 2 bars)."""
        now = datetime.now()
        start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        df = self._generator.generate_bars(
            symbols=[symbol],
            start=start,
            end=now,
            frequency=frequency,
        )
        last_row = df.iloc[-1]
        return Bar(
            symbol=last_row["symbol"],
            timestamp=last_row["timestamp"],
            open=last_row["open"],
            high=last_row["high"],
            low=last_row["low"],
            close=last_row["close"],
            volume=last_row["volume"],
            frequency=last_row["frequency"],
            vwap=last_row.get("vwap"),
        )

    def subscribe_bars(self, symbols: list[str], frequency: BarFrequency) -> None:
        """Synthetic provider: no-op (no streaming)."""
        self._subscribed[frequency] = symbols

    @property
    def is_connected(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "synthetic"
