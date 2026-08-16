import unittest

from f1nance.risk_management.backtest import var_backtest
from f1nance.risk_management.limits import Limit, check_limit, check_limits
from f1nance.risk_management.stress import Scenario, reverse_stress, stress_test


class LimitTest(unittest.TestCase):
    def test_max_breach(self):
        r = check_limit(Limit("gross", "max_gross_exposure", 1.5), 1.8)
        self.assertTrue(r.breached)
        self.assertAlmostEqual(r.utilization, 1.2)
        self.assertAlmostEqual(r.headroom, -0.3)

    def test_max_ok(self):
        r = check_limit(Limit("gross", "max_gross_exposure", 1.5), 1.0)
        self.assertFalse(r.breached)
        self.assertAlmostEqual(r.utilization, 1.0 / 1.5)
        self.assertAlmostEqual(r.headroom, 0.5)

    def test_min_breach(self):
        r = check_limit(Limit("div", "effective_n", 5, direction="min"), 4.0)
        self.assertTrue(r.breached)
        self.assertAlmostEqual(r.utilization, 1.25)
        self.assertAlmostEqual(r.headroom, -1.0)

    def test_min_ok(self):
        r = check_limit(Limit("div", "effective_n", 5, direction="min"), 10.0)
        self.assertFalse(r.breached)
        self.assertAlmostEqual(r.utilization, 0.5)
        self.assertAlmostEqual(r.headroom, 5.0)

    def test_degenerate_limits(self):
        with self.assertRaises(ValueError):
            Limit("", "m", 1.0)
        with self.assertRaises(ValueError):
            Limit("n", "m", 1.0, direction="sideways")
        with self.assertRaises(ValueError):
            Limit("n", "m", 0.0)  # max needs a positive threshold
        with self.assertRaises(ValueError):
            Limit("n", "m", 0.0, direction="min")  # min needs non-zero threshold

    def test_check_min_zero_current_raises(self):
        with self.assertRaises(ValueError):
            check_limit(Limit("div", "effective_n", 5, direction="min"), 0.0)

    def test_non_finite_current_raises(self):
        with self.assertRaises(ValueError):
            check_limit(Limit("gross", "max_gross_exposure", 1.5), float("inf"))


class CheckLimitsTest(unittest.TestCase):
    def test_report(self):
        report = check_limits(
            [
                Limit("gross", "max_gross_exposure", 1.5),
                Limit("hhi", "hhi", 0.25),
                Limit("div", "effective_n", 5, direction="min"),
            ],
            {"max_gross_exposure": 1.8, "hhi": 0.30, "effective_n": 4},
        )
        self.assertEqual(report.breach_count, 3)
        self.assertEqual(report.breached, ["gross", "hhi", "div"])
        self.assertEqual(report.worst.name, "div")  # min-limit utilization 5/4 = 1.25 is the max
        self.assertAlmostEqual(report.worst.utilization, 1.25)

    def test_unknown_metric_raises(self):
        with self.assertRaises(ValueError):
            check_limits(
                [Limit("gross", "max_gross_exposure", 1.5)],
                {"hhi": 0.2},  # max_gross_exposure not supplied
            )

    def test_no_limits_raises(self):
        with self.assertRaises(ValueError):
            check_limits([], {})


class StressTest(unittest.TestCase):
    def test_known_pnl(self):
        outcomes = stress_test(
            {"equity": 3_000_000.0, "rates": 1_000_000.0},
            [Scenario("crash", {"equity": -0.30})],
            nav=5_000_000.0,
        )
        self.assertEqual(len(outcomes), 1)
        self.assertAlmostEqual(outcomes[0].pnl, -900_000.0)
        self.assertAlmostEqual(outcomes[0].pnl_pct, -0.18)
        self.assertEqual(outcomes[0].worst, "equity")
        self.assertAlmostEqual(outcomes[0].contributions["equity"], -900_000.0)
        self.assertAlmostEqual(outcomes[0].contributions["rates"], 0.0)

    def test_shock_on_unexposed_factor_is_zero(self):
        outcomes = stress_test(
            {"equity": 1_000_000.0},
            [Scenario("rate_shock", {"rates": 0.02})],
        )
        self.assertAlmostEqual(outcomes[0].pnl, 0.0)

    def test_worst_is_most_negative_contribution(self):
        outcomes = stress_test(
            {"equity": 1_000_000.0, "rates": 2_000_000.0},
            [Scenario("both", {"equity": -0.10, "rates": -0.20})],
        )
        self.assertEqual(outcomes[0].worst, "rates")

    def test_pnl_pct_none_without_nav(self):
        outcomes = stress_test(
            {"equity": 1_000_000.0}, [Scenario("crash", {"equity": -0.30})]
        )
        self.assertIsNone(outcomes[0].pnl_pct)

    def test_degenerate_raises(self):
        with self.assertRaises(ValueError):
            stress_test({}, [Scenario("x", {"equity": -0.1})])
        with self.assertRaises(ValueError):
            stress_test({"equity": 1.0}, [])
        with self.assertRaises(ValueError):
            stress_test({"equity": 1.0}, [Scenario("x", {"equity": -0.1})], nav=0.0)
        with self.assertRaises(ValueError):
            stress_test({"equity": 1.0}, [Scenario("x", {"equity": -0.1})], nav=-5.0)
        with self.assertRaises(ValueError):
            Scenario("x", {})


class ReverseStressTest(unittest.TestCase):
    def test_long_exposure_negative_shock(self):
        r = reverse_stress({"equity": 3_000_000.0}, "equity", 600_000.0)
        self.assertAlmostEqual(r.shock, -0.20)
        self.assertAlmostEqual(r.exposure, 3_000_000.0)

    def test_short_exposure_positive_shock(self):
        r = reverse_stress({"equity": -500_000.0}, "equity", 50_000.0)
        self.assertAlmostEqual(r.shock, 0.10)

    def test_unknown_factor_raises(self):
        with self.assertRaises(ValueError):
            reverse_stress({"equity": 1.0}, "fx", 1.0)

    def test_zero_exposure_raises(self):
        with self.assertRaises(ValueError):
            reverse_stress({"equity": 0.0}, "equity", 1.0)

    def test_non_positive_target_loss_raises(self):
        with self.assertRaises(ValueError):
            reverse_stress({"equity": 1.0}, "equity", 0.0)
        with self.assertRaises(ValueError):
            reverse_stress({"equity": 1.0}, "equity", -1.0)


class VarBacktestTest(unittest.TestCase):
    # n=100 VaR forecasts at 0.05, realized returns engineered for a breach count.
    def _series(self, exceptions):
        # exceptions: list of 0/1; return -0.10 (breach) or 0.01 (no breach) for var 0.05
        var = [0.05] * len(exceptions)
        returns = [-0.10 if e == 1 else 0.01 for e in exceptions]
        return var, returns

    def test_zero_exceptions_closed_form(self):
        var, returns = self._series([0] * 100)
        bt = var_backtest(var, returns, confidence=0.95)
        self.assertEqual(bt.exceptions, 0)
        # LR = -2 * n * ln(1 - p)
        self.assertAlmostEqual(bt.kupiec_lr, -2.0 * 100 * __import__("math").log(0.95), places=6)
        # zero breaches at 95% over 100 obs is miscalibrated -> rejected
        self.assertTrue(bt.kupiec_reject)

    def test_all_exceptions_closed_form(self):
        var, returns = self._series([1] * 100)
        bt = var_backtest(var, returns, confidence=0.95)
        self.assertEqual(bt.exceptions, 100)
        self.assertAlmostEqual(bt.kupiec_lr, -2.0 * 100 * __import__("math").log(0.05), places=6)
        self.assertTrue(bt.kupiec_reject)

    def test_kupiec_reference_value(self):
        # the classic example: 100 obs, 8 exceptions at 95%
        var, returns = self._series([1] * 8 + [0] * 92)
        bt = var_backtest(var, returns, confidence=0.95)
        self.assertAlmostEqual(bt.kupiec_lr, 1.615808, places=6)
        self.assertAlmostEqual(bt.kupiec_pvalue, 0.203677, places=6)
        self.assertFalse(bt.kupiec_reject)  # 0.20 > 0.05

    def test_exact_expected_exceptions_accept(self):
        var, returns = self._series([1] * 5 + [0] * 95)
        bt = var_backtest(var, returns, confidence=0.95)
        self.assertAlmostEqual(bt.kupiec_lr, 0.0, places=9)
        self.assertAlmostEqual(bt.kupiec_pvalue, 1.0, places=9)
        self.assertFalse(bt.kupiec_reject)

    def test_more_exceptions_larger_lr(self):
        _, r5 = self._series([1] * 5 + [0] * 95)
        _, r20 = self._series([1] * 20 + [0] * 80)
        bt5 = var_backtest([0.05] * 100, r5)
        bt20 = var_backtest([0.05] * 100, r20)
        self.assertGreater(bt20.kupiec_lr, bt5.kupiec_lr)
        self.assertTrue(bt20.kupiec_reject)

    def test_independence_alternating_rejects(self):
        var, returns = self._series([1, 0, 1, 0, 1, 0, 1, 0])
        bt = var_backtest(var, returns, confidence=0.5, significance=0.05)
        # exceptions strictly alternate -> perfectly anti-clustered -> reject
        self.assertGreater(bt.christoffersen_lr, 0.0)
        self.assertTrue(bt.christoffersen_reject)

    def test_independence_all_same_state_degnerate(self):
        var, returns = self._series([0] * 20)
        bt = var_backtest(var, returns, confidence=0.5)
        self.assertEqual(bt.christoffersen_lr, 0.0)
        self.assertEqual(bt.christoffersen_pvalue, 1.0)
        self.assertFalse(bt.christoffersen_reject)

    def test_conditional_coverage_is_sum(self):
        var, returns = self._series([1] * 8 + [0] * 92)
        bt = var_backtest(var, returns, confidence=0.95)
        self.assertAlmostEqual(
            bt.conditional_coverage_lr,
            bt.kupiec_lr + bt.christoffersen_lr,
            places=9,
        )

    def test_degenerate_raises(self):
        with self.assertRaises(ValueError):
            var_backtest([], [])
        with self.assertRaises(ValueError):
            var_backtest([0.05, 0.05], [0.01])
        with self.assertRaises(ValueError):
            var_backtest([0.05], [0.01], confidence=0.0)
        with self.assertRaises(ValueError):
            var_backtest([0.05], [0.01], confidence=1.0)
        with self.assertRaises(ValueError):
            var_backtest([0.05], [0.01], significance=0.0)
        with self.assertRaises(ValueError):
            var_backtest([-0.05], [0.01])  # negative VaR forecast


if __name__ == "__main__":
    unittest.main()
