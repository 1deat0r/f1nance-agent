import unittest

from f1nance.quant.linear import ols, ridge


class SolveFitTest(unittest.TestCase):
    def test_exact_fit_intercept(self):
        # y = 1 + 2x exactly: x = [1,2,3,4] -> y = [3,5,7,9]
        r = ols([3.0, 5.0, 7.0, 9.0], [[1.0, 2.0, 3.0, 4.0]])
        self.assertAlmostEqual(r.coefficients[0], 1.0, places=9)
        self.assertAlmostEqual(r.coefficients[1], 2.0, places=9)
        self.assertAlmostEqual(r.r_squared, 1.0, places=9)
        for res in r.residuals:
            self.assertAlmostEqual(res, 0.0, places=9)
        self.assertAlmostEqual(r.residual_std, 0.0, places=9)
        # perfectly identified -> standard errors zero -> t-stats undefined
        self.assertEqual(r.t_statistics, [None, None])
        self.assertEqual(r.feature_names, ["intercept", "x0"])

    def test_exact_fit_no_intercept(self):
        # y = 2x, no intercept
        r = ols([2.0, 4.0, 6.0, 8.0], [[1.0, 2.0, 3.0, 4.0]], fit_intercept=False)
        self.assertAlmostEqual(r.coefficients[0], 2.0, places=9)
        self.assertEqual(r.feature_names, ["x0"])

    def test_multiple_regression(self):
        # y = 2*x0 + 3*x1, x0=[1,2,3,4], x1=[0,1,0,1] -> y=[2,7,6,11]
        r = ols([2.0, 7.0, 6.0, 11.0], [[1.0, 2.0, 3.0, 4.0], [0.0, 1.0, 0.0, 1.0]])
        self.assertAlmostEqual(r.coefficients[0], 0.0, places=9)
        self.assertAlmostEqual(r.coefficients[1], 2.0, places=9)
        self.assertAlmostEqual(r.coefficients[2], 3.0, places=9)
        self.assertAlmostEqual(r.r_squared, 1.0, places=9)

    def test_feature_names(self):
        r = ols([3.0, 5.0, 7.0, 9.0], [[1.0, 2.0, 3.0, 4.0]], feature_names=["mkt"])
        self.assertEqual(r.feature_names, ["intercept", "mkt"])


class InferenceTest(unittest.TestCase):
    def test_t_stats_consistent_with_se(self):
        # noisy line: y ~ 1 + 2x + small noise
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        y = [3.1, 5.0, 7.2, 8.9, 11.1, 12.9]
        r = ols(y, [x])
        self.assertGreater(r.r_squared, 0.99)
        self.assertLess(r.adjusted_r_squared, r.r_squared)
        for b, se, t in zip(r.coefficients, r.standard_errors, r.t_statistics):
            self.assertGreater(se, 0.0)
            self.assertIsNotNone(t)
            assert t is not None
            self.assertAlmostEqual(t, b / se, places=9)
        self.assertAlmostEqual(r.coefficients[1], 2.0, delta=0.2)

    def test_adjusted_less_than_r_squared(self):
        r = ols([3.0, 5.0, 7.0, 9.0, 11.0], [[1.0, 2.0, 3.0, 4.0, 5.0]])
        self.assertLessEqual(r.adjusted_r_squared, r.r_squared + 1e-12)


class RidgeTest(unittest.TestCase):
    def test_ridge_zero_equals_ols(self):
        r = ridge([2.0, 4.0, 6.0, 8.0], [[1.0, 2.0, 3.0, 4.0]], lam=0.0)
        self.assertAlmostEqual(r.coefficients[1], 2.0, places=9)

    def test_ridge_shrinks_coefficients(self):
        # exact y = 2x; a large penalty shrinks the slope toward zero
        r = ridge([2.0, 4.0, 6.0, 8.0], [[1.0, 2.0, 3.0, 4.0]], lam=1000.0)
        self.assertLess(abs(r.coefficients[1]), 0.5)
        self.assertGreater(abs(r.coefficients[1]), 0.0)
        # ridge deliberately omits OLS-style inference
        self.assertEqual(r.standard_errors, [])
        self.assertEqual(r.t_statistics, [])

    def test_ridge_negative_penalty_raises(self):
        with self.assertRaises(ValueError):
            ridge([2.0, 4.0, 6.0, 8.0], [[1.0, 2.0, 3.0, 4.0]], lam=-1.0)


class DegenerateTest(unittest.TestCase):
    def test_collinear_features_raise(self):
        with self.assertRaises(ValueError):
            ols([1.0, 2.0, 3.0], [[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]])

    def test_constant_response_raises(self):
        with self.assertRaises(ValueError):
            ols([1.0, 1.0, 1.0, 1.0], [[1.0, 2.0, 3.0, 4.0]])

    def test_insufficient_observations_raise(self):
        with self.assertRaises(ValueError):
            ols([1.0, 2.0], [[1.0, 2.0], [3.0, 4.0]])

    def test_feature_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            ols([1.0, 2.0, 3.0], [[1.0, 2.0]])

    def test_empty_response_raises(self):
        with self.assertRaises(ValueError):
            ols([], [])


if __name__ == "__main__":
    unittest.main()
