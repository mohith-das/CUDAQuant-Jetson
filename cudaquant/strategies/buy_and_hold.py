"""Baseline buy-and-hold strategy (always fully long)."""

from __future__ import annotations

import pandas as pd

from cudaquant.strategies.base import Strategy


class BuyAndHold(Strategy):
    """Returns a full long position signal (1) for every bar."""

    def __init__(self, name: str = "buy_and_hold", parameters: dict | None = None):
        super().__init__(name, parameters or {})

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        return pd.Series(1.0, index=data.index)
