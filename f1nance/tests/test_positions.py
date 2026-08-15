import unittest

from f1nance.portfolio.positions import (
    Exposure,
    InvalidPortfolio,
    MissingFxRate,
    Portfolio,
    Position,
    rebalance_trades,
)


class MarketValueTest(unittest.TestCase):
    def test_usd_positions_sum(self):
        port = Portfolio(positions=[
            Position("AAPL", 10, 200.0),
            Position("MSFT", 5, 400.0),
        ])
        self.assertEqual(port.market_value(), 4000.0)

    def test_fx_conversion(self):
        port = Portfolio(
            positions=[Position("SAP", 10, 100.0, currency="EUR")],
            fx_rates={"EUR": 1.1},
        )
        self.assertEqual(port.market_value(), 1100.0)
        self.assertEqual(port.position_base_values()["SAP"], 1100.0)

    def test_missing_fx_raises(self):
        port = Portfolio(positions=[Position("SAP", 10, 100.0, currency="EUR")])
        with self.assertRaises(MissingFxRate):
            port.market_value()

    def test_cash_included_in_nav(self):
        port = Portfolio(
            positions=[Position("AAPL", 10, 100.0)],
            cash={"USD": 1000.0},
        )
        self.assertEqual(port.market_value(), 2000.0)
        self.assertEqual(port.market_value(include_cash=False), 1000.0)

    def test_cash_in_foreign_currency(self):
        port = Portfolio(cash={"EUR": 100.0}, fx_rates={"EUR": 1.2})
        self.assertEqual(port.cash_base_value(), 120.0)


class WeightsTest(unittest.TestCase):
    def test_weights_sum_to_one_with_cash(self):
        port = Portfolio(
            positions=[Position("AAPL", 10, 100.0)],
            cash={"USD": 1000.0},
        )
        weights = port.weights()
        self.assertAlmostEqual(weights["AAPL"], 0.5)
        self.assertAlmostEqual(weights["CASH"], 0.5)
        self.assertAlmostEqual(sum(weights.values()), 1.0)

    def test_weights_exclude_cash(self):
        port = Portfolio(
            positions=[Position("AAPL", 10, 100.0)],
            cash={"USD": 1000.0},
        )
        weights = port.weights(include_cash=False)
        self.assertNotIn("CASH", weights)
        self.assertAlmostEqual(weights["AAPL"], 0.5)

    def test_cash_weight(self):
        port = Portfolio(
            positions=[Position("AAPL", 15, 100.0)],
            cash={"USD": 500.0},
        )
        # nav = 1500 + 500 = 2000; cash weight = 0.25
        self.assertAlmostEqual(port.cash_weight(), 0.25)

    def test_zero_nav_raises(self):
        port = Portfolio()
        with self.assertRaises(InvalidPortfolio):
            port.weights()


class ExposureTest(unittest.TestCase):
    def test_long_only_fully_invested(self):
        port = Portfolio(positions=[Position("AAPL", 10, 100.0)])
        exp = port.exposure()
        self.assertAlmostEqual(exp.long, 1.0)
        self.assertAlmostEqual(exp.short, 0.0)
        self.assertAlmostEqual(exp.gross, 1.0)
        self.assertAlmostEqual(exp.net, 1.0)

    def test_long_short(self):
        port = Portfolio(positions=[
            Position("AAPL", 15, 100.0),   # +1500
            Position("TSLA", -5, 100.0),   # -500
        ])
        exp = port.exposure()
        self.assertAlmostEqual(exp.long, 1.5)
        self.assertAlmostEqual(exp.short, 0.5)
        self.assertAlmostEqual(exp.gross, 2.0)
        self.assertAlmostEqual(exp.net, 1.0)

    def test_exposure_by_class(self):
        port = Portfolio(positions=[
            Position("AAPL", 10, 100.0, asset_class="equity"),
            Position("TLT", 10, 100.0, asset_class="fixed_income"),
        ])
        by_class = port.exposure_by_class()
        self.assertAlmostEqual(by_class["equity"], 0.5)
        self.assertAlmostEqual(by_class["fixed_income"], 0.5)


class CashDragTest(unittest.TestCase):
    def test_cash_drag(self):
        port = Portfolio(
            positions=[Position("AAPL", 15, 100.0)],
            cash={"USD": 500.0},  # cash weight 0.25
        )
        self.assertAlmostEqual(port.cash_drag(0.08), 0.02)
        self.assertAlmostEqual(port.cash_drag(0.08, cash_return=0.04), 0.01)


class PositionTest(unittest.TestCase):
    def test_unrealized_pnl(self):
        p = Position("AAPL", 10, 210.0, cost_basis=180.0)
        self.assertEqual(p.unrealized_pnl(), 300.0)

    def test_unrealized_pnl_unknown_without_basis(self):
        p = Position("AAPL", 10, 210.0)
        self.assertIsNone(p.unrealized_pnl())

    def test_is_short(self):
        self.assertTrue(Position("TSLA", -5, 100.0).is_short())
        self.assertFalse(Position("AAPL", 5, 100.0).is_short())


class RebalanceTest(unittest.TestCase):
    def test_rebalance_trades(self):
        deltas = rebalance_trades({"A": 6000.0, "B": 4000.0}, {"A": 0.5, "B": 0.5})
        self.assertAlmostEqual(deltas["A"], -1000.0)
        self.assertAlmostEqual(deltas["B"], 1000.0)

    def test_rebalance_sells_removed_asset(self):
        deltas = rebalance_trades({"A": 3000.0, "B": 7000.0}, {"B": 1.0})
        self.assertAlmostEqual(deltas["A"], -3000.0)
        self.assertAlmostEqual(deltas["B"], 3000.0)

    def test_rebalance_buys_new_asset(self):
        deltas = rebalance_trades({"A": 10000.0}, {"A": 0.9, "B": 0.1})
        self.assertAlmostEqual(deltas["A"], -1000.0)
        self.assertAlmostEqual(deltas["B"], 1000.0)

    def test_rebalance_weights_must_sum_to_one(self):
        with self.assertRaises(InvalidPortfolio):
            rebalance_trades({"A": 10000.0}, {"A": 0.9})

    def test_rebalance_zero_total_raises(self):
        with self.assertRaises(InvalidPortfolio):
            rebalance_trades({}, {"A": 1.0})


if __name__ == "__main__":
    unittest.main()
