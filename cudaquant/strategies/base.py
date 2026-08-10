"""Base strategy interface.

A strategy maps OHLCV data to a position signal series with values in
``(-1, 0, 1)``. ``generate_signals`` MUST NOT look ahead: it may only use
information available at each row's decision time. The backtest engine is the
enforcement point — it only ever hands a strategy the rows up to the current
bar — but strategies must also be correct when called standalone.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    """Base strategy interface."""

    def __init__(self, name: str, parameters: dict):
        self.name = name
        self.parameters = dict(parameters)
        self.version = 1

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate position signals (-1, 0, 1) from OHLCV data.

        MUST NOT look ahead in the data. Returns a Series with the same index
        as ``data``; the value at each row is the target position decided
        using only rows up to and including that row.
        """

    def get_info(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "parameters": self.parameters,
            "type": self.__class__.__name__,
        }
