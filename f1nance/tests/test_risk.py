import math
import unittest

from f1nance.portfolio.risk import (
    annualized_return,
    annualized_volatility,
    beta,
    concentration,
    correlation,
    covariance,
    cvar_historical,
    downside_deviation,
    drawdown_series,
    effective_n,
    hhi,
    log_returns,
    max_drawdown,
    returns_from_prices,
    sharpe_ratio,
    simple_returns,
    sortino_ratio,
    var_historical,
    var_parametric,
    volatility,
)


class ReturnsTest(unittest.TestCase):
    def test_simple_returns(self):
        r = simple_returns([100.0, 110.0, 99.0])
        self.assertAlmostEqual(r[0], 0.1)
        self.assertAlmostEqual(r[1], -0.1)

    def test_log_returns(self):
        r = log_returns([100.0, 110.0])
        self.assertAlmostEqual(r[0], math.log(1.1))

    def test_log_returns_requires_positive(self):
        with self.assertRaises(ValueError):
            log_returns([100.0, -50.0])

    def test_returns_from_prices_method(self):
        self.assertAlmostEqual(returns_from_prices([100.0, 120.0], "simple")[0], 0.2)
        self.assertAlmostEqual(returns_from_prices([100.0, 120.0], "log")[0], math.log(1.2))

    def test_unknown_method_raises(self):
        with self.assertRaises(ValueError):
            returns_from_prices([1.0, 2.0], "weird")


class VolatilityTest(unittest.TestCase):
    def test_volatility_known(self):
        # population stddev of [0.01, -0.01, 0.02, -0.02]
        self.assertAlmostEqual(
            volatility([0.01, -0.01, 0.02, -0.02]),
            math.sqrt(0.00025),
        )

    def test_annualized_volatility(self):
        r = [0.01, -0.01, 0.02, -0.02]
        self.assertAlmostEqual(
            annualized_volatility(r, 252),
            math.sqrt(0.00025) * math.sqrt(252),
        )

    def test_volatility_needs_two_returns(self):
        with self.assertRaises(ValueError):
            volatility([0.01])

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            volatility([])


class ReturnMetricsTest(unittest.TestCase):
    def test_annualized_return_geometric(self):
        # two periods of +10%: growth 1.21 over 2 periods
        r = annualized_return([0.1, 0.1], periods_per_year=2, geometric=True)
        self.assertAlmostEqual(r, 0.21)

    def test_annualized_return_arithmetic(self):
        r = annualized_return([0.1, 0.1], periods_per_year=2, geometric=False)
        self.assertAlmostEqual(r, 0.2)

    def test_sharpe_ratio_known(self):
        # [0.01, 0.02, 0.01, 0.02]: mean 0.015, pstdev 0.005
        s = sharpe_ratio([0.01, 0.02, 0.01, 0.02], periods_per_year=252)
        self.assertAlmostEqual(s, math.sqrt(252) * 0.015 / 0.005)

    def test_sharpe_zero_vol_raises(self):
        with self.assertRaises(ValueError):
            sharpe_ratio([0.01, 0.01, 0.01], periods_per_year=252)

    def test_downside_deviation(self):
        # returns [0.10, 0.10, -0.05], target 0: only -0.05 is below
        dd = downside_deviation([0.10, 0.10, -0.05], target=0.0)
        self.assertAlmostEqual(dd, math.sqrt(0.0025 / 3))

    def test_sortino_ratio_known(self):
        # [0.10, 0.10, -0.05]: mean 0.05, downside dev 0.05/sqrt(3)
        s = sortino_ratio([0.10, 0.10, -0.05], target=0.0, periods_per_year=1)
        self.assertAlmostEqual(s, math.sqrt(3.0), places=6)


class DrawdownTest(unittest.TestCase):
    def test_drawdown_series(self):
        dd = drawdown_series([100.0, 120.0, 90.0, 110.0])
        self.assertAlmostEqual(dd[0], 0.0)
        self.assertAlmostEqual(dd[1], 0.0)
        self.assertAlmostEqual(dd[2], 90.0 / 120.0 - 1.0)
        self.assertAlmostEqual(dd[3], 110.0 / 120.0 - 1.0)

    def test_max_drawdown(self):
        self.assertAlmostEqual(max_drawdown([100.0, 120.0, 90.0, 110.0]), 0.25)

    def test_max_drawdown_monotonic_up(self):
        self.assertAlmostEqual(max_drawdown([100.0, 110.0, 120.0]), 0.0)

    def test_max_drawdown_empty(self):
        self.assertEqual(max_drawdown([]), 0.0)


class TailRiskTest(unittest.TestCase):
    RETURNS = [-0.10, -0.05, 0.00, 0.05, 0.10]

    def test_var_historical(self):
        # confidence 0.60 -> tail 0.40 -> 2nd smallest = -0.05 -> VaR 0.05
        self.assertAlmostEqual(var_historical(self.RETURNS, confidence=0.60), 0.05)

    def test_cvar_historical(self):
        # tail below -0.05: {-0.10, -0.05}, mean -0.075 -> CVaR 0.075
        self.assertAlmostEqual(cvar_historical(self.RETURNS, confidence=0.60), 0.075)

    def test_var_confidence_bounds(self):
        with self.assertRaises(ValueError):
            var_historical(self.RETURNS, confidence=0.0)
        with self.assertRaises(ValueError):
            var_historical(self.RETURNS, confidence=1.0)

    def test_var_empty_raises(self):
        with self.assertRaises(ValueError):
            var_historical([])

    def test_var_parametric(self):
        # [0.01, -0.01]: mean 0, pstdev 0.01; z(0.95) * 0.01 (periods=1)
        v = var_parametric([0.01, -0.01], confidence=0.95, periods_per_year=1)
        self.assertAlmostEqual(v, 1.6448536269514722 * 0.01, places=6)


class RelativeRiskTest(unittest.TestCase):
    BENCH = [0.01, -0.01, 0.02, -0.02]

    def test_beta_twice_benchmark(self):
        b = beta([0.02, -0.02, 0.04, -0.04], self.BENCH)
        self.assertAlmostEqual(b, 2.0)

    def test_beta_mismatched_lengths_raises(self):
        with self.assertRaises(ValueError):
            beta([0.01, 0.02], self.BENCH)

    def test_beta_zero_variance_raises(self):
        with self.assertRaises(ValueError):
            beta([0.0, 0.0, 0.0], [0.0, 0.0, 0.0])

    def test_correlation_perfect(self):
        self.assertAlmostEqual(correlation(self.BENCH, [2 * x for x in self.BENCH]), 1.0)

    def test_correlation_negative(self):
        self.assertAlmostEqual(correlation(self.BENCH, [-x for x in self.BENCH]), -1.0)

    def test_covariance_scales(self):
        # cov(r, 2*r) = 2 * var(r)
        self.assertAlmostEqual(covariance(self.BENCH, [2 * x for x in self.BENCH]),
                               2 * _pvariance(self.BENCH))


def _pvariance(xs):
    n = len(xs)
    m = sum(xs) / n
    return sum((x - m) ** 2 for x in xs) / n


class ConcentrationTest(unittest.TestCase):
    def test_hhi_equal_weight(self):
        self.assertAlmostEqual(hhi([0.5, 0.5]), 0.5)

    def test_effective_n(self):
        self.assertAlmostEqual(effective_n([0.5, 0.5]), 2.0)
        self.assertAlmostEqual(effective_n([1.0]), 1.0)

    def test_concentration_summary(self):
        c = concentration([0.5, 0.3, 0.2])
        self.assertAlmostEqual(c["hhi"], 0.5 * 0.5 + 0.3 * 0.3 + 0.2 * 0.2)
        self.assertAlmostEqual(c["effective_n"], 1.0 / c["hhi"])
        self.assertAlmostEqual(c["top_weight"], 0.5)
        self.assertAlmostEqual(c["top3_weight"], 1.0)

    def test_concentration_ignores_nonpositive(self):
        c = concentration([0.6, 0.4, -0.2, 0.0])
        self.assertAlmostEqual(c["top_weight"], 0.6)
        self.assertAlmostEqual(c["top3_weight"], 1.0)


if __name__ == "__main__":
    unittest.main()
