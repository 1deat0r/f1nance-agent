import unittest

from f1nance.fixed_income.bonds import (
    bond_price,
    cashflows,
    duration_and_convexity,
    ytm,
)
from f1nance.fixed_income.curves import (
    bootstrap_spot_curve,
    discount_factor,
    forward_rate,
    interpolate_spot,
    pv,
    pv_curve,
    spot_rate,
)


class DiscountFactorTest(unittest.TestCase):
    def test_annual(self):
        self.assertAlmostEqual(discount_factor(0.05, 2, compounding=1), 1 / 1.05**2, places=9)

    def test_semiannual(self):
        self.assertAlmostEqual(discount_factor(0.05, 2, compounding=2), 1 / 1.025**4, places=9)

    def test_continuous(self):
        import math

        self.assertAlmostEqual(discount_factor(0.05, 2, "continuous"), math.exp(-0.10), places=9)

    def test_negative_time_raises(self):
        with self.assertRaises(ValueError):
            discount_factor(0.05, -1)

    def test_nonpositive_discount_factor_raises(self):
        with self.assertRaises(ValueError):
            discount_factor(-2.5, 1, compounding=2)  # rate <= -m

    def test_bad_compounding_raises(self):
        with self.assertRaises(ValueError):
            discount_factor(0.05, 1, compounding=0)


class SpotRateTest(unittest.TestCase):
    def test_inverts_discount_factor(self):
        self.assertAlmostEqual(spot_rate(discount_factor(0.06, 3, 2), 3, 2), 0.06, places=9)

    def test_nonpositive_df_raises(self):
        with self.assertRaises(ValueError):
            spot_rate(0.0, 1)

    def test_nonpositive_time_raises(self):
        with self.assertRaises(ValueError):
            spot_rate(0.9, 0)


class ForwardRateTest(unittest.TestCase):
    def test_flat_curve(self):
        self.assertAlmostEqual(forward_rate(0.05, 0.05, 1, 2), 0.05, places=6)

    def test_upward_curve(self):
        self.assertAlmostEqual(forward_rate(0.02, 0.03, 1, 2), 0.040049505, places=6)

    def test_inverted_curve_is_negative_not_an_error(self):
        self.assertLess(forward_rate(0.05, 0.005, 1, 2), 0.0)

    def test_continuous_forward(self):
        import math

        # f = (r2*t2 - r1*t1) / (t2 - t1)
        self.assertAlmostEqual(
            forward_rate(0.02, 0.04, 1, 3, "continuous"), (0.04 * 3 - 0.02 * 1) / 2, places=9
        )

    def test_t1_not_before_t2_raises(self):
        with self.assertRaises(ValueError):
            forward_rate(0.02, 0.03, 2, 1)


class PresentValueTest(unittest.TestCase):
    def test_flat_rate_annuity(self):
        # 5, 5, 105 at 4% semiannual: 5/1.02^2 + 5/1.02^4 + 105/1.02^6
        self.assertAlmostEqual(pv([5, 5, 105], [1, 2, 3], 0.04), 102.66206617, places=6)

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            pv([5, 5], [1, 2, 3], 0.04)

    def test_pv_curve_matches_flat_rate_on_flat_curve(self):
        flat = pv([5, 5, 105], [1, 2, 3], 0.04)
        curved = pv_curve([5, 5, 105], [1, 2, 3], [1, 2, 3], [0.04, 0.04, 0.04])
        self.assertAlmostEqual(flat, curved, places=9)

    def test_interpolate_midpoint(self):
        self.assertAlmostEqual(interpolate_spot([1, 2, 3], [0.02, 0.03, 0.04], 2.5), 0.035, places=9)

    def test_interpolate_exact_tenor(self):
        self.assertAlmostEqual(interpolate_spot([1, 2, 3], [0.02, 0.03, 0.04], 2.0), 0.03, places=9)

    def test_interpolate_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            interpolate_spot([1, 2, 3], [0.02, 0.03, 0.04], 0.5)
        with self.assertRaises(ValueError):
            interpolate_spot([1, 2, 3], [0.02, 0.03, 0.04], 4.0)

    def test_interpolate_non_increasing_tenors_raise(self):
        with self.assertRaises(ValueError):
            interpolate_spot([1, 2, 2], [0.02, 0.03, 0.04], 1.5)


class BootstrapTest(unittest.TestCase):
    def test_flat_curve(self):
        tenors, spots = bootstrap_spot_curve([1, 2, 3], [0.05, 0.05, 0.05])
        self.assertEqual(tenors, [1.0, 2.0, 3.0])
        for s in spots:
            self.assertAlmostEqual(s, 0.05, places=6)

    def test_upward_curve_spots_above_par(self):
        tenors, spots = bootstrap_spot_curve([1, 2, 3], [0.02, 0.03, 0.04])
        self.assertAlmostEqual(spots[0], 0.02, places=6)
        self.assertAlmostEqual(spots[1], 0.030151504, places=6)
        self.assertAlmostEqual(spots[2], 0.040549757, places=6)
        self.assertGreater(spots[1], 0.03)
        self.assertGreater(spots[2], 0.04)

    def test_non_consecutive_tenors_raise(self):
        with self.assertRaises(ValueError):
            bootstrap_spot_curve([1, 3], [0.02, 0.03])

    def test_nonpositive_discount_factor_raises(self):
        with self.assertRaises(ValueError):
            bootstrap_spot_curve([1, 2], [0.02, 2.0])

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            bootstrap_spot_curve([1, 2], [0.02])


class CashflowTest(unittest.TestCase):
    def test_schedule(self):
        cfs = cashflows(0.05, 1, 100, 2)
        self.assertEqual(len(cfs), 2)
        self.assertAlmostEqual(cfs[0][0], 0.5, places=9)
        self.assertAlmostEqual(cfs[0][1], 2.5, places=9)
        self.assertAlmostEqual(cfs[1][0], 1.0, places=9)
        self.assertAlmostEqual(cfs[1][1], 102.5, places=9)

    def test_nonpositive_maturity_raises(self):
        with self.assertRaises(ValueError):
            cashflows(0.05, 0, 100, 2)

    def test_fractional_period_raises(self):
        with self.assertRaises(ValueError):
            cashflows(0.05, 0.3, 100, 2)


class BondPriceTest(unittest.TestCase):
    def test_par_bond(self):
        self.assertAlmostEqual(bond_price(0.05, 10, 0.05), 100.0, places=6)

    def test_premium_bond(self):
        self.assertAlmostEqual(bond_price(0.05, 10, 0.04), 108.17571667, places=6)

    def test_discount_bond(self):
        self.assertAlmostEqual(bond_price(0.05, 10, 0.06), 92.56126257, places=6)

    def test_zero_coupon(self):
        self.assertAlmostEqual(bond_price(0.0, 1, 0.05), 95.18143962, places=6)

    def test_nonpositive_yield_discount_factor_raises(self):
        with self.assertRaises(ValueError):
            bond_price(0.05, 1, -3)  # r = -1.5, 1+r <= 0


class BondYtmTest(unittest.TestCase):
    def test_par_yields_coupon(self):
        self.assertAlmostEqual(ytm(100.0, 0.05, 10), 0.05, places=6)

    def test_premium_price_yields_below_coupon(self):
        self.assertAlmostEqual(ytm(108.17, 0.05, 10), 0.040006671, places=5)

    def test_discount_price_yields_above_coupon(self):
        self.assertAlmostEqual(ytm(92.56126257, 0.05, 10), 0.06, places=5)

    def test_nonpositive_price_raises(self):
        with self.assertRaises(ValueError):
            ytm(0.0, 0.05, 10)


class BondRiskTest(unittest.TestCase):
    def test_zero_coupon_identity(self):
        r = duration_and_convexity(0.0, 1, 0.05)
        self.assertAlmostEqual(r.macaulay_duration, 1.0, places=9)
        self.assertAlmostEqual(r.modified_duration, 1 / 1.025, places=9)
        self.assertAlmostEqual(r.convexity, 6 / (1.025**2 * 4), places=9)
        self.assertAlmostEqual(r.dv01, bond_price(0.0, 1, 0.05) * (1 / 1.025) * 0.0001, places=9)

    def test_coupon_bond_duration_below_maturity(self):
        r = duration_and_convexity(0.05, 10, 0.04)
        self.assertLess(r.macaulay_duration, 10.0)
        self.assertAlmostEqual(r.modified_duration, 7.922486268, places=6)
        self.assertAlmostEqual(r.convexity, 75.472466789, places=6)
        self.assertGreater(r.convexity, 0.0)

    def test_degenerate_yield_raises(self):
        with self.assertRaises(ValueError):
            duration_and_convexity(0.05, 1, -3)


if __name__ == "__main__":
    unittest.main()
