"""Order model and validation for the F1NANCE execution layer.

An order is described once (instrument, side, quantity, type, prices, time in
force) and validated before anything is sent. Structural errors — a negative
quantity, a limit order with no limit, a stop with no trigger — raise. With a
market price, ``assess`` additionally flags a *marketable* limit (already
crossing the market) and a stop placed on the *wrong side* (already
triggered).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"


@dataclass
class Order:
    instrument: str
    side: Side
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY


@dataclass
class OrderAssessment:
    order: Order
    marketable: bool
    stop_wrong_side: bool
    warnings: list = field(default_factory=list)


def validate_order(order: Order) -> None:
    """Raise on structurally invalid orders (missing/negative prices, qty)."""
    if not (order.instrument or "").strip():
        raise ValueError("instrument is required")
    if order.quantity <= 0:
        raise ValueError("quantity must be positive")
    if order.order_type is OrderType.LIMIT and order.limit_price is None:
        raise ValueError("a limit order requires a limit price")
    if order.order_type is OrderType.STOP and order.stop_price is None:
        raise ValueError("a stop order requires a stop price")
    if order.order_type is OrderType.STOP_LIMIT and (
        order.limit_price is None or order.stop_price is None
    ):
        raise ValueError("a stop-limit order requires both a stop and a limit price")
    if order.limit_price is not None and order.limit_price <= 0:
        raise ValueError("limit price must be positive")
    if order.stop_price is not None and order.stop_price <= 0:
        raise ValueError("stop price must be positive")


def assess(order: Order, market_price: Optional[float] = None) -> OrderAssessment:
    """Validate an order and assess it against an optional market price."""
    validate_order(order)
    if market_price is None:
        return OrderAssessment(
            order=order,
            marketable=False,
            stop_wrong_side=False,
            warnings=["no market price supplied; marketability and stop-side not assessed"],
        )
    if market_price <= 0:
        raise ValueError("market price must be positive")

    marketable = False
    if order.limit_price is not None:
        if order.side is Side.BUY:
            marketable = order.limit_price >= market_price
        else:
            marketable = order.limit_price <= market_price

    stop_wrong_side = False
    if order.stop_price is not None:
        if order.side is Side.BUY:
            # a buy stop triggers on a rise, so it must sit above the market
            stop_wrong_side = order.stop_price <= market_price
        else:
            # a sell stop triggers on a fall, so it must sit below the market
            stop_wrong_side = order.stop_price >= market_price

    warnings = []
    if marketable:
        warnings.append("limit already crosses the market; it will fill immediately")
    if stop_wrong_side:
        warnings.append("stop is on the wrong side of the market; it is already triggered")

    return OrderAssessment(
        order=order,
        marketable=marketable,
        stop_wrong_side=stop_wrong_side,
        warnings=warnings,
    )
