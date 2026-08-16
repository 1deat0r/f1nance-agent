import math
import unittest

from f1nance.derivatives.binomial import binomial_price
from f1nance.derivatives.black_scholes import (
    black_scholes,
    greeks,
    implied_volatility,
    normal_cdf,
    normal_pdf,
)


class NormalTest(unittest.TestCase):
    def test_cdf_symmetric_around_zero(self):
        self.assertAlmostEqual(normal_cdf(0.0), 0.5, places=9)
        self.assertAlmostEqual(normal_cdf(1.0), 0.841344746, places=7)
        self.assertAlmostEqual(normal_cdf(-1.0), 1 - 0.841344746, places=7)
        self.assertAlmostEqual(normal_cdf(1.96), 0.975002105, places=7)

    def test_pdf(self):
        self.assertAlmostEqual(normal_pdf(0.0), 1 / math.sqrt(2 * math.pi), places=9)
        self.assertAlmostEqual(normal_pdf(1.0), 0.241970724, places=7)
        self.assertAlmostEqual(normal_pdf(1.0), normal_pdf(-1.0), places=9)


class BlackScholesPriceTest(unittest.TestCase):
    def test_hull_call(self):
        # Hull's worked example: S=42, K=40, T=0.5, r=10%, sigma=20%
        p = black_scholes("call", 42, 40, 0.5, 0.10, 0.20)
        self.assertAlmostEqual(p.price, 4.759422, places=6)

    def test_hull_put(self):
        p = black_scholes("put", 42, 40, 0.5, 0.10, 0.20)
        self.assertAlmostEqual(p.price, 0.808599, places=6)

    def test_canonical_atm(self):
        call = black_scholes("call", 100, 100, 1, 0.05, 0.20)
        put = black_scholes("put", 100, 100, 1, 0.05, 0.20)
        self.assertAlmostEqual(call.price, 10.450584, places=6)
        self.assertAlmostEqual(put.price, 5.573526, places=6)

    def test_dividend_yield(self):
        call = black_scholes("call", 50, 52, 2, 0.03, 0.25, q=0.02)
        put = black_scholes("put", 50, 52, 2, 0.03, 0.25, q=0.02)
        self.assertAlmostEqual(call.price, 6.349932, places=6)
        self.assertAlmostEqual(put.price, 7.282216, places=6)

    def test_call_put_case_insensitive(self):
        self.assertAlmostEqual(
            black_scholes("CALL", 42, 40, 0.5, 0.10, 0.20).price,
            black_scholes("call", 42, 40, 0.5, 0.10, 0.20).price,
            places=9,
        )

    def test_put_call_parity(self):
        # C - P = S e^{-qT} - K e^{-rT}  (a real contract, not a snapshot)
        for S, K, T, r, sigma, q in (
            (100, 100, 1, 0.05, 0.20, 0.0),
            (42, 40, 0.5, 0.10, 0.20, 0.0),
            (50, 52, 2, 0.03, 0.25, 0.02),
            (120, 90, 0.25, 0.01, 0.40, 0.01),
        ):
            call = black_scholes("call", S, K, T, r, sigma, q).price
            put = black_scholes("put", S, K, T, r, sigma, q).price
            rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
            self.assertAlmostEqual(call - put, rhs, places=9, msg=f"S={S} K={K}")

    def test_negative_rate_is_legal(self):
        # negative rates are a real market state, not an error
        p = black_scholes("call", 100, 100, 1, -0.01, 0.20)
        self.assertGreater(p.price, 0.0)

    def test_degenerate_raises(self):
        with self.assertRaises(ValueError):
            black_scholes("call", 0, 100, 1, 0.05, 0.20)  # non-positive spot
        with self.assertRaises(ValueError):
            black_scholes("call", 100, 0, 1, 0.05, 0.20)  # non-positive strike
        with self.assertRaises(ValueError):
            black_scholes("call", 100, 100, 0, 0.05, 0.20)  # zero time
        with self.assertRaises(ValueError):
            black_scholes("call", 100, 100, 1, 0.05, 0.0)  # zero vol
        with self.assertRaises(ValueError):
            black_scholes("call", 100, 100, 1, 0.05, -0.20)  # negative vol
        with self.assertRaises(ValueError):
            black_scholes("straddle", 100, 100, 1, 0.05, 0.20)  # bad kind


class GreeksTest(unittest.TestCase):
    def test_hull_reference_values(self):
        g = greeks("call", 42, 40, 0.5, 0.10, 0.20)
        self.assertAlmostEqual(g.delta, 0.779131, places=6)
        self.assertAlmostEqual(g.gamma, 0.049963, places=6)
        self.assertAlmostEqual(g.vega, 8.813415, places=6)
        self.assertAlmostEqual(g.rho, 13.982046, places=6)
        self.assertAlmostEqual(g.theta, -4.559092, places=6)

    def test_put_delta_negative(self):
        g = greeks("put", 42, 40, 0.5, 0.10, 0.20)
        self.assertAlmostEqual(g.delta, -0.220869, places=6)

    def test_delta_put_call_relation(self):
        # delta_call - delta_put = e^{-qT}
        for q, T in ((0.0, 1.0), (0.02, 2.0)):
            dc = greeks("call", 100, 100, T, 0.05, 0.20, q=q).delta
            dp = greeks("put", 100, 100, T, 0.05, 0.20, q=q).delta
            self.assertAlmostEqual(dc - dp, math.exp(-q * T), places=9)

    def test_gamma_and_vega_symmetric(self):
        for cp in ("call", "put"):
            g = greeks(cp, 100, 100, 1, 0.05, 0.20)
            self.assertGreater(g.gamma, 0.0)
            self.assertGreater(g.vega, 0.0)
        gc = greeks("call", 100, 100, 1, 0.05, 0.20)
        gp = greeks("put", 100, 100, 1, 0.05, 0.20)
        self.assertAlmostEqual(gc.gamma, gp.gamma, places=9)
        self.assertAlmostEqual(gc.vega, gp.vega, places=9)

    def test_theta_negative_for_long(self):
        # a long option loses value to time decay (all else equal)
        for cp in ("call", "put"):
            g = greeks(cp, 100, 100, 1, 0.05, 0.20)
            self.assertLess(g.theta, 0.0)

    def test_degenerate_raises(self):
        with self.assertRaises(ValueError):
            greeks("call", 100, 100, 1, 0.05, 0.0)


class ImpliedVolatilityTest(unittest.TestCase):
    def test_known_value(self):
        iv = implied_volatility(10.450584, "call", 100, 100, 1, 0.05)
        self.assertAlmostEqual(iv, 0.20, places=5)

    def test_round_trip(self):
        for sigma in (0.10, 0.20, 0.35, 0.60):
            for cp in ("call", "put"):
                price = black_scholes(cp, 100, 100, 1, 0.05, sigma).price
                iv = implied_volatility(price, cp, 100, 100, 1, 0.05)
                self.assertAlmostEqual(iv, sigma, places=6, msg=f"{cp} sigma={sigma}")

    def test_round_trip_with_dividend(self):
        price = black_scholes("call", 50, 52, 2, 0.03, 0.25, q=0.02).price
        iv = implied_volatility(price, "call", 50, 52, 2, 0.03, q=0.02)
        self.assertAlmostEqual(iv, 0.25, places=6)

    def test_below_intrinsic_raises(self):
        # a call worth less than S - K e^{-rT} is an arbitrage, no real vol
        with self.assertRaises(ValueError):
            implied_volatility(0.5, "call", 100, 90, 1, 0.05)

    def test_above_upper_bound_raises(self):
        # a call priced above the deep-ITM limit (S e^{-qT}) has no real vol
        with self.assertRaises(ValueError):
            implied_volatility(150.0, "call", 100, 100, 1, 0.05)

    def test_nonpositive_price_raises(self):
        with self.assertRaises(ValueError):
            implied_volatility(0.0, "call", 100, 100, 1, 0.05)


class BinomialTest(unittest.TestCase):
    def test_european_converges_to_black_scholes(self):
        # CRR converges O(1/n); assert the error shrinks as the lattice refines
        bs = black_scholes("call", 100, 100, 1, 0.05, 0.20).price
        err50 = abs(binomial_price("call", 100, 100, 1, 0.05, 0.20, steps=50) - bs)
        err500 = abs(binomial_price("call", 100, 100, 1, 0.05, 0.20, steps=500) - bs)
        err1000 = abs(binomial_price("call", 100, 100, 1, 0.05, 0.20, steps=1000) - bs)
        self.assertLess(err500, err50)
        self.assertLess(err1000, err500)
        self.assertAlmostEqual(
            binomial_price("call", 100, 100, 1, 0.05, 0.20, steps=1000), bs, places=2
        )

    def test_put_converges(self):
        bs = black_scholes("put", 42, 40, 0.5, 0.10, 0.20).price
        tree = binomial_price("put", 42, 40, 0.5, 0.10, 0.20, steps=1000)
        self.assertAlmostEqual(tree, bs, places=2)

    def test_american_put_exceeds_european(self):
        # early exercise has value for a put; the American price is not below
        eu = binomial_price("put", 42, 40, 0.5, 0.10, 0.20, steps=200)
        am = binomial_price("put", 42, 40, 0.5, 0.10, 0.20, steps=200, american=True)
        self.assertGreater(am, eu)

    def test_american_call_equals_european_without_dividend(self):
        # no dividends -> no early exercise for a call
        eu = binomial_price("call", 100, 100, 1, 0.05, 0.20, steps=200)
        am = binomial_price("call", 100, 100, 1, 0.05, 0.20, steps=200, american=True)
        self.assertAlmostEqual(eu, am, places=6)

    def test_at_the_money_intrinsic_lower_bound(self):
        # a call is never worth less than its intrinsic value
        tree = binomial_price("call", 100, 90, 1, 0.05, 0.20, steps=200)
        self.assertGreaterEqual(tree, 100 - 90)

    def test_degenerate_raises(self):
        with self.assertRaises(ValueError):
            binomial_price("call", 100, 100, 1, 0.05, 0.20, steps=0)
        with self.assertRaises(ValueError):
            binomial_price("call", 100, 100, 1, 0.05, 0.0)  # zero vol
        with self.assertRaises(ValueError):
            binomial_price("call", 0, 100, 1, 0.05, 0.20)  # non-positive spot

    def test_extreme_rate_small_vol_raises(self):
        # risk-neutral probability leaves [0, 1] -> tree would arbitrage
        with self.assertRaises(ValueError):
            binomial_price("call", 100, 100, 1, 5.0, 0.001, steps=2)


if __name__ == "__main__":
    unittest.main()
