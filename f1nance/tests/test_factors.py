import unittest

from f1nance.quant.factors import (
    capm,
    cross_sectional_rank,
    cross_sectional_zscore,
    momentum_predictor,
    multi_factor,
    trailing_return,
)


class CapmTest(unittest.TestCase):
    MARKET = [0.01, -0.01, 0.02, -0.02]

    def test_beta_two_exact(self):
        # asset = 2 * market exactly (no alpha)
        m = capm([0.02, -0.02, 0.04, -0.04], self.MARKET)
        self.assertAlmostEqual(m.alpha, 0.0, places=9)
        self.assertAlmostEqual(m.exposures["market"], 2.0, places=9)
        self.assertAlmostEqual(m.r_squared, 1.0, places=9)
        self.assertAlmostEqual(m.residual_volatility, 0.0, places=9)

    def test_alpha_intercept(self):
        # asset = 0.01 + 2 * market -> alpha 0.01, annualized 0.01 * 252
        asset = [0.01 + 2 * r for r in self.MARKET]
        m = capm(asset, self.MARKET, periods_per_year=252)
        self.assertAlmostEqual(m.alpha, 0.01, places=9)
        self.assertAlmostEqual(m.annualized_alpha, 0.01 * 252, places=9)
        self.assertAlmostEqual(m.exposures["market"], 2.0, places=9)

    def test_rf_subtracted(self):
        # with a risk-free rate, excess = asset - rf_per is what is regressed
        m = capm([0.02, -0.02, 0.04, -0.04], self.MARKET, risk_free_rate=0.0, periods_per_year=252)
        self.assertAlmostEqual(m.alpha, 0.0, places=9)

    def test_mismatched_lengths_raise(self):
        with self.assertRaises(ValueError):
            capm([0.01, 0.02], self.MARKET)

    def test_too_few_observations_raise(self):
        with self.assertRaises(ValueError):
            capm([0.01, 0.02], [0.01, 0.02])


class MultiFactorTest(unittest.TestCase):
    def test_two_factor_exact(self):
        # asset = 2*f1 + 3*f2; f1 linear, f2 quadratic -> full-rank with intercept
        f1 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        f2 = [1.0, 4.0, 9.0, 16.0, 25.0, 36.0]
        asset = [5.0, 16.0, 33.0, 56.0, 85.0, 120.0]
        m = multi_factor(asset, {"f1": f1, "f2": f2})
        self.assertAlmostEqual(m.alpha, 0.0, places=9)
        self.assertAlmostEqual(m.exposures["f1"], 2.0, places=9)
        self.assertAlmostEqual(m.exposures["f2"], 3.0, places=9)
        self.assertAlmostEqual(m.r_squared, 1.0, places=9)
        self.assertEqual(m.n_factors, 2)

    def test_empty_factors_raise(self):
        with self.assertRaises(ValueError):
            multi_factor([0.01, 0.02, 0.03, 0.04], {})

    def test_factor_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            multi_factor([0.01, 0.02, 0.03, 0.04], {"f1": [0.01, 0.02]})


class CrossSectionTest(unittest.TestCase):
    def test_zscore(self):
        rows = [{"A": 0.0, "B": 2.0}, {"A": 1.0, "B": 3.0}]
        out = cross_sectional_zscore(rows)
        # each row: mean 1, std 1 -> A=-1, B=+1 (population stddev)
        self.assertAlmostEqual(out[0]["A"], -1.0, places=9)
        self.assertAlmostEqual(out[0]["B"], 1.0, places=9)
        self.assertAlmostEqual(out[1]["A"], -1.0, places=9)
        self.assertAlmostEqual(out[1]["B"], 1.0, places=9)

    def test_zscore_zero_variance_raises(self):
        with self.assertRaises(ValueError):
            cross_sectional_zscore([{"A": 5.0, "B": 5.0}])

    def test_zscore_single_asset_raises(self):
        with self.assertRaises(ValueError):
            cross_sectional_zscore([{"A": 1.0}])

    def test_rank(self):
        out = cross_sectional_rank([{"A": 1.0, "B": 2.0, "C": 3.0}])
        self.assertAlmostEqual(out[0]["A"], 0.0, places=9)
        self.assertAlmostEqual(out[0]["B"], 0.5, places=9)
        self.assertAlmostEqual(out[0]["C"], 1.0, places=9)

    def test_rank_ties_averaged(self):
        out = cross_sectional_rank([{"A": 1.0, "B": 1.0, "C": 3.0}])
        self.assertAlmostEqual(out[0]["A"], 0.25, places=9)
        self.assertAlmostEqual(out[0]["B"], 0.25, places=9)
        self.assertAlmostEqual(out[0]["C"], 1.0, places=9)

    def test_mismatched_assets_raise(self):
        with self.assertRaises(ValueError):
            cross_sectional_zscore([{"A": 1.0, "B": 2.0}, {"A": 1.0, "C": 2.0}])


class MomentumTest(unittest.TestCase):
    def test_trailing_return(self):
        self.assertAlmostEqual(trailing_return([0.1, 0.1], 2), 0.21, places=9)

    def test_trailing_return_lookback_too_big_raises(self):
        with self.assertRaises(ValueError):
            trailing_return([0.1], 2)

    def test_trailing_return_bad_lookback_raises(self):
        with self.assertRaises(ValueError):
            trailing_return([0.1, 0.1], 0)

    def test_predictor_picks_top(self):
        pred = momentum_predictor(lookback=2, top_k=1)
        w = pred({"A": [0.1, 0.1], "B": [-0.1, -0.1]})
        self.assertAlmostEqual(w["A"], 1.0, places=9)
        self.assertAlmostEqual(w["B"], 0.0, places=9)

    def test_predictor_equal_weights_top_k(self):
        pred = momentum_predictor(lookback=2, top_k=2)
        w = pred({"A": [0.1, 0.1], "B": [-0.1, -0.1]})
        self.assertAlmostEqual(w["A"], 0.5, places=9)
        self.assertAlmostEqual(w["B"], 0.5, places=9)

    def test_predictor_top_k_exceeds_universe_raises(self):
        pred = momentum_predictor(lookback=2, top_k=3)
        with self.assertRaises(ValueError):
            pred({"A": [0.1, 0.1], "B": [-0.1, -0.1]})


if __name__ == "__main__":
    unittest.main()
