"""Abstract base classes for provider interfaces."""

from abc import ABC, abstractmethod

import pandas as pd

from cudaquant.data.schemas import Account, Bar, BarFrequency, Order, Position


class MarketDataProvider(ABC):
    """Abstract interface for market data providers."""

    @abstractmethod
    def get_bars(
        self,
        symbols: list[str],
        start,
        end,
        frequency: BarFrequency,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV bars."""

    @abstractmethod
    def get_latest_bar(self, symbol: str, frequency: BarFrequency) -> Bar:
        """Get the most recent bar for a symbol."""

    @abstractmethod
    def subscribe_bars(self, symbols: list[str], frequency: BarFrequency) -> None:
        """Subscribe to streaming bar updates."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the provider is currently connected."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""


class Broker(ABC):
    """Abstract interface for brokers."""

    @abstractmethod
    def submit_order(self, order: Order) -> str:
        """Submit an order. Returns order_id."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True if cancelled."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Get current positions."""

    @abstractmethod
    def get_account(self) -> Account:
        """Get current account state."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the broker is currently connected."""


class NewsProvider(ABC):
    """Abstract interface for news providers."""

    @abstractmethod
    def get_news(self, symbols: list[str], start, end) -> list[dict]:
        """Fetch news articles for symbols in date range."""


class LLMProvider(ABC):
    """Abstract interface for LLM providers (research agent, advisory only)."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate a text response from the LLM."""
