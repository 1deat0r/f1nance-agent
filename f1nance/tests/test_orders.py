import unittest

from f1nance.execution.orders import (
    Order,
    OrderType,
    Side,
    TimeInForce,
    assess,
    validate_order,
)


def order(**kw):
    defaults = dict(
        instrument="AAPL", side=Side.BUY, quantity=100,
        order_type=OrderType.MARKET,
    )
    defaults.update(kw)
    return Order(**defaults)


class ValidateOrderTest(unittest.TestCase):
    def test_valid_market_order(self):
        validate_order(order())  # should not raise

    def test_missing_instrument_raises(self):
        with self.assertRaises(ValueError):
            validate_order(order(instrument=""))

    def test_negative_quantity_raises(self):
        with self.assertRaises(ValueError):
            validate_order(order(quantity=-1))

    def test_zero_quantity_raises(self):
        with self.assertRaises(ValueError):
            validate_order(order(quantity=0))

    def test_limit_order_requires_limit_price(self):
        with self.assertRaises(ValueError):
            validate_order(order(order_type=OrderType.LIMIT, limit_price=None))

    def test_stop_order_requires_stop_price(self):
        with self.assertRaises(ValueError):
            validate_order(order(order_type=OrderType.STOP, stop_price=None))

    def test_stop_limit_requires_both_prices(self):
        with self.assertRaises(ValueError):
            validate_order(order(order_type=OrderType.STOP_LIMIT,
                                 stop_price=100.0, limit_price=None))

    def test_nonpositive_limit_price_raises(self):
        with self.assertRaises(ValueError):
            validate_order(order(order_type=OrderType.LIMIT, limit_price=0))

    def test_nonpositive_stop_price_raises(self):
        with self.assertRaises(ValueError):
            validate_order(order(order_type=OrderType.STOP, stop_price=-5))


class AssessOrderTest(unittest.TestCase):
    def test_buy_limit_above_market_is_marketable(self):
        a = assess(order(order_type=OrderType.LIMIT, limit_price=195.0),
                   market_price=192.0)
        self.assertTrue(a.marketable)
        self.assertFalse(a.stop_wrong_side)

    def test_buy_limit_below_market_not_marketable(self):
        a = assess(order(order_type=OrderType.LIMIT, limit_price=190.0),
                   market_price=192.0)
        self.assertFalse(a.marketable)

    def test_sell_limit_below_market_is_marketable(self):
        a = assess(order(side=Side.SELL, order_type=OrderType.LIMIT,
                         limit_price=190.0), market_price=192.0)
        self.assertTrue(a.marketable)

    def test_buy_stop_below_market_wrong_side(self):
        a = assess(order(order_type=OrderType.STOP, stop_price=190.0),
                   market_price=192.0)
        self.assertTrue(a.stop_wrong_side)

    def test_buy_stop_above_market_ok(self):
        a = assess(order(order_type=OrderType.STOP, stop_price=195.0),
                   market_price=192.0)
        self.assertFalse(a.stop_wrong_side)

    def test_sell_stop_above_market_wrong_side(self):
        a = assess(order(side=Side.SELL, order_type=OrderType.STOP,
                         stop_price=195.0), market_price=192.0)
        self.assertTrue(a.stop_wrong_side)

    def test_sell_stop_below_market_ok(self):
        a = assess(order(side=Side.SELL, order_type=OrderType.STOP,
                         stop_price=190.0), market_price=192.0)
        self.assertFalse(a.stop_wrong_side)

    def test_no_market_price_warns(self):
        a = assess(order(order_type=OrderType.LIMIT, limit_price=190.0))
        self.assertFalse(a.marketable)
        self.assertTrue(any("no market price" in w for w in a.warnings))

    def test_nonpositive_market_price_raises(self):
        with self.assertRaises(ValueError):
            assess(order(), market_price=0)

    def test_stop_limit_wrong_side(self):
        a = assess(order(order_type=OrderType.STOP_LIMIT,
                         stop_price=190.0, limit_price=189.0),
                   market_price=192.0)
        self.assertTrue(a.stop_wrong_side)


if __name__ == "__main__":
    unittest.main()
