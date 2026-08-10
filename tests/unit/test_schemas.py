"""Pydantic schema validation tests.

Targets ``cudaquant.data.schemas``: ``Bar``, ``Order``, ``Fill``.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from cudaquant.data.schemas import Bar, BarFrequency, Fill, Order, OrderSide, OrderType

TS = datetime(2024, 1, 2, 14, 30)


def _valid_bar() -> dict:
    return {
        "symbol": "AAPL",
        "timestamp": TS,
        "open": 100.0,
        "high": 105.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 1000,
        "frequency": BarFrequency.MINUTE_1,
    }


def _valid_order() -> dict:
    return {
        "symbol": "AAPL",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "qty": 10,
    }


def _valid_fill() -> dict:
    return {
        "order_id": "ord-001",
        "symbol": "AAPL",
        "side": OrderSide.BUY,
        "qty": 10,
        "price": 100.0,
        "timestamp": TS,
    }


# ── Bar ────────────────────────────────────────────────────────────────────


def test_bar_valid_passes():
    bar = Bar(**_valid_bar())
    assert bar.symbol == "AAPL"
    assert bar.close == 101.0


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
def test_bar_negative_price_raises(field):
    payload = _valid_bar()
    payload[field] = -1.0
    with pytest.raises(ValidationError):
        Bar(**payload)


def test_bar_zero_price_raises():
    payload = _valid_bar()
    payload["close"] = 0.0
    with pytest.raises(ValidationError):
        Bar(**payload)


def test_bar_negative_volume_raises():
    payload = _valid_bar()
    payload["volume"] = -100
    with pytest.raises(ValidationError):
        Bar(**payload)


def test_bar_timestamp_must_be_datetime():
    payload = _valid_bar()
    payload["timestamp"] = "not-a-date"  # clearly invalid
    with pytest.raises(ValidationError):
        Bar(**payload)


def test_bar_missing_required_field_raises():
    payload = _valid_bar()
    del payload["close"]
    with pytest.raises(ValidationError):
        Bar(**payload)


# ── Order ───────────────────────────────────────────────────────────────────


def test_order_valid_passes():
    order = Order(**_valid_order())
    assert order.qty == 10
    assert order.side == OrderSide.BUY


def test_order_negative_quantity_raises():
    payload = _valid_order()
    payload["qty"] = -1
    with pytest.raises(ValidationError):
        Order(**payload)


def test_order_zero_quantity_raises():
    payload = _valid_order()
    payload["qty"] = 0
    with pytest.raises(ValidationError):
        Order(**payload)


def test_order_negative_price_raises():
    payload = _valid_order()
    payload["limit_price"] = -5.0
    with pytest.raises(ValidationError):
        Order(**payload)


def test_order_missing_symbol_raises():
    payload = _valid_order()
    del payload["symbol"]
    with pytest.raises(ValidationError):
        Order(**payload)


def test_order_invalid_side_raises():
    payload = _valid_order()
    payload["side"] = "hold"
    with pytest.raises(ValidationError):
        Order(**payload)


# ── Fill ────────────────────────────────────────────────────────────────────


def test_fill_valid_passes():
    fill = Fill(**_valid_fill())
    assert fill.price == 100.0


def test_fill_negative_quantity_raises():
    payload = _valid_fill()
    payload["qty"] = -10
    with pytest.raises(ValidationError):
        Fill(**payload)


def test_fill_negative_price_raises():
    payload = _valid_fill()
    payload["price"] = -1.0
    with pytest.raises(ValidationError):
        Fill(**payload)


def test_fill_timestamp_must_be_datetime():
    payload = _valid_fill()
    payload["timestamp"] = "not-a-datetime"
    with pytest.raises(ValidationError):
        Fill(**payload)
