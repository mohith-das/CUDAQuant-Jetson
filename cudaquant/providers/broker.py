"""Broker adapter ABC — separate from MarketDataProvider.

Market data reading and order execution are different concerns with
different risk profiles. This interface covers the execution side only.
"""

from abc import ABC, abstractmethod

from cudaquant.data.schemas import Account, Order, Position


class BrokerAdapter(ABC):
    """Abstract interface for broker execution.

    Separate from MarketDataProvider. Every implementation must be used
    through execution/order_service.py — never call submit_order() directly.
    """

    @abstractmethod
    def get_account(self) -> Account:
        """Get current account state (cash, portfolio value, buying power)."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Get current open positions."""

    @abstractmethod
    def submit_order(self, order: Order) -> str:
        """Submit an order. Returns order_id.

        WARNING: Never call this directly. Use execution/order_service.py
        which enforces config gates, RiskGovernor, and KillSwitch first.
        """

    @abstractmethod
    def get_order(self, order_id: str) -> dict:
        """Get order status by ID."""

    @abstractmethod
    def list_orders(self, status: str = "all", limit: int = 50) -> list[dict]:
        """List recent orders."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True if cancelled."""

    @abstractmethod
    def cancel_all_orders(self) -> int:
        """Cancel all open orders. Returns count cancelled."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the broker is connected and authenticated."""
