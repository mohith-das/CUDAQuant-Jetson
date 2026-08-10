"""Alpaca broker — paper and live trading via Alpaca Markets API.

Uses the official alpaca-py SDK. All order submission must go through
execution/order_service.py — this class's submit_order() is NOT for
direct external use.

Environment: ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER
"""

import logging

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaSide
from alpaca.trading.enums import TimeInForce
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

from cudaquant.config.settings import settings
from cudaquant.data.schemas import Account, Order, OrderSide, OrderType, Position
from cudaquant.providers.broker import BrokerAdapter

logger = logging.getLogger(__name__)


class AlpacaBroker(BrokerAdapter):
    """Alpaca trading API broker — paper or live.

    Paper/live is determined by settings.ALPACA_PAPER:
    - True → https://paper-api.alpaca.markets
    - False → https://api.alpaca.markets

    Authentication via ALPACA_API_KEY and ALPACA_SECRET_KEY from settings.
    """

    def __init__(self):
        key = settings.ALPACA_API_KEY
        secret = settings.ALPACA_SECRET_KEY
        paper = settings.ALPACA_PAPER

        if not key or not secret:
            self._client = None
            self._connected = False
            logger.warning("AlpacaBroker: no API credentials configured")
            return

        self._client = TradingClient(
            api_key=key,
            secret_key=secret,
            paper=paper,
        )
        self._connected = self._verify_connection()

    def _verify_connection(self) -> bool:
        """Verify API credentials by fetching account."""
        if self._client is None:
            return False
        try:
            self._client.get_account()
            return True
        except Exception as e:
            logger.error("AlpacaBroker: connection verification failed: %s", e)
            return False

    def get_account(self) -> Account:
        if self._client is None:
            return Account(cash=0.0, portfolio_value=0.0, buying_power=0.0)
        acct = self._client.get_account()
        return Account(
            cash=float(acct.cash),
            portfolio_value=float(acct.portfolio_value),
            buying_power=float(acct.buying_power),
        )

    def get_positions(self) -> list[Position]:
        if self._client is None:
            return []
        positions = []
        for p in self._client.get_all_positions():
            positions.append(Position(
                symbol=p.symbol,
                qty=int(float(p.qty)),
                avg_entry_price=float(p.avg_entry_price),
                market_value=float(p.market_value) if p.market_value else None,
                unrealized_pnl=float(p.unrealized_pl) if p.unrealized_pl else None,
            ))
        return positions

    def submit_order(self, order: Order) -> str:
        """Submit an order. NOT for direct use — use OrderService."""
        if self._client is None:
            raise RuntimeError("AlpacaBroker: not connected (no credentials)")

        side = AlpacaSide.BUY if order.side == OrderSide.BUY else AlpacaSide.SELL

        if order.order_type == OrderType.MARKET:
            req = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.qty,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
        else:
            req = LimitOrderRequest(
                symbol=order.symbol,
                qty=order.qty,
                side=side,
                limit_price=order.limit_price or 0.0,
                time_in_force=TimeInForce.DAY,
            )

        result = self._client.submit_order(req)
        return str(result.id)

    def get_order(self, order_id: str) -> dict:
        if self._client is None:
            return {"id": order_id, "status": "unknown"}
        o = self._client.get_order_by_id(order_id)
        return {
            "id": str(o.id),
            "symbol": o.symbol,
            "side": str(o.side),
            "qty": str(o.qty) if o.qty else "0",
            "filled_qty": str(o.filled_qty) if o.filled_qty else "0",
            "status": str(o.status),
            "type": str(o.type),
            "limit_price": str(o.limit_price) if o.limit_price else None,
            "submitted_at": str(o.submitted_at) if o.submitted_at else None,
        }

    def list_orders(self, status: str = "all", limit: int = 50) -> list[dict]:
        if self._client is None:
            return []
        from alpaca.trading.requests import GetOrdersRequest
        filter_req = GetOrdersRequest(status=status, limit=limit)
        orders = self._client.get_orders(filter=filter_req)
        return [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "side": str(o.side),
                "qty": str(o.qty) if o.qty else "0",
                "filled_qty": str(o.filled_qty) if o.filled_qty else "0",
                "status": str(o.status),
                "submitted_at": str(o.submitted_at) if o.submitted_at else None,
            }
            for o in orders
        ]

    def cancel_order(self, order_id: str) -> bool:
        if self._client is None:
            return False
        try:
            self._client.cancel_order_by_id(order_id)
            return True
        except Exception:
            return False

    def cancel_all_orders(self) -> int:
        if self._client is None:
            return 0
        result = self._client.cancel_orders()
        return len(result) if result else 0

    @property
    def is_connected(self) -> bool:
        return self._connected
