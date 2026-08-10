"""Trading strategies — entry/exit logic, signal generation."""

from cudaquant.strategies.base import Strategy
from cudaquant.strategies.buy_and_hold import BuyAndHold

__all__ = ["Strategy", "BuyAndHold"]
