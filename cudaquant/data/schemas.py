"""Pydantic v2 models for market data — bars, trades, orders, positions."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class BarFrequency(str, Enum):
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "60m"
    DAY_1 = "1d"


class Bar(BaseModel):
    """OHLCV bar for a single symbol at a single timestamp."""

    symbol: str
    timestamp: datetime  # UTC
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    frequency: BarFrequency
    vwap: float | None = None
    trade_count: int | None = None


class Trade(BaseModel):
    """Individual trade/print."""

    symbol: str
    timestamp: datetime
    price: float = Field(ge=0)
    size: float = Field(ge=0)
    exchange: str = ""
    conditions: list[str] | None = None


class Quote(BaseModel):
    """Bid/ask quote."""

    symbol: str
    timestamp: datetime
    bid: float = Field(ge=0)
    ask: float = Field(ge=0)
    bid_size: int = Field(ge=0)
    ask_size: int = Field(ge=0)


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class Order(BaseModel):
    """Order to be submitted to a broker."""

    symbol: str
    side: OrderSide
    order_type: OrderType
    qty: float = Field(gt=0)
    limit_price: float | None = Field(default=None, ge=0)
    time_in_force: str = "day"


class Fill(BaseModel):
    """Execution fill for an order."""

    order_id: str
    symbol: str
    side: OrderSide
    qty: float = Field(gt=0)
    price: float = Field(ge=0)
    timestamp: datetime
    commission: float = 0.0


class Position(BaseModel):
    """Current position in a symbol."""

    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float | None = None
    unrealized_pnl: float | None = None


class Account(BaseModel):
    """Account state snapshot."""

    cash: float
    portfolio_value: float
    buying_power: float
    positions: list[Position] = []
