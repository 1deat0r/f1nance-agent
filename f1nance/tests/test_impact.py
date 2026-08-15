import math
import unittest

from f1nance.execution.impact import (
    estimate_cost,
    market_impact_bps,
    participation_rate,
)


class ParticipationTest(unittest.TestCase):
    def test_basic(self):
        self.assertAlmostEqual(participation_rate(1_000_000.0, 10_000_000.0), 0.1)

    def test_zero_notional_raises(self):
        with self.assertRaises(ValueError):
            participation_rate(0, 100.0)

    def test_zero_adv_raises(self):
        with self.assertRaises(ValueError):
            participation_rate(100.0, 0)


class MarketImpactTest(unittest.TestCase):
    def test_sqrt_law(self):
        # doubling participation scales impact by sqrt(2)
        i1 = market_impact_bps(0.01, sigma_daily_bps=100.0, coefficient=0.1)
        i2 = market_impact_bps(0.02, sigma_daily_bps=100.0, coefficient=0.1)
        self.assertAlmostEqual(i2 / i1, math.sqrt(2.0), places=9)

    def test_negative_sigma_raises(self):
        with self.assertRaises(ValueError):
            market_impact_bps(0.01, sigma_daily_bps=-1.0)

    def test_negative_coefficient_raises(self):
        with self.assertRaises(ValueError):
            market_impact_bps(0.01, coefficient=-1.0)

    def test_zero_participation_raises(self):
        with self.assertRaises(ValueError):
            market_impact_bps(0.0)


class EstimateCostTest(unittest.TestCase):
    def test_components_sum(self):
        c = estimate_cost(1_000_000.0, 10_000_000.0, spread_bps=10.0, fee_bps=2.0)
        # half-spread = 5, participation = 0.1, impact = 100 * 0.1 * sqrt(0.1)
        expected_impact = 100.0 * 0.1 * math.sqrt(0.1)
        self.assertAlmostEqual(c.spread_bps, 5.0)
        self.assertAlmostEqual(c.market_impact_bps, expected_impact)
        self.assertAlmostEqual(c.total_bps, 5.0 + expected_impact + 2.0)
        self.assertAlmostEqual(c.total_cost, 1_000_000.0 * c.total_bps / 10_000.0)

    def test_participation_over_100pct_raises(self):
        with self.assertRaises(ValueError):
            estimate_cost(2_000_000.0, 1_000_000.0)

    def test_impact_zone_flag(self):
        c = estimate_cost(20_000_000.0, 100_000_000.0)  # 20% participation
        self.assertTrue(c.impact_zone)
        self.assertTrue(any("impact" in w for w in c.warnings))

    def test_small_trade_no_impact_zone(self):
        c = estimate_cost(1_000_000.0, 100_000_000.0)  # 1%
        self.assertFalse(c.impact_zone)

    def test_negative_spread_raises(self):
        with self.assertRaises(ValueError):
            estimate_cost(1_000_000.0, 10_000_000.0, spread_bps=-1.0)

    def test_negative_fee_raises(self):
        with self.assertRaises(ValueError):
            estimate_cost(1_000_000.0, 10_000_000.0, fee_bps=-1.0)


if __name__ == "__main__":
    unittest.main()
