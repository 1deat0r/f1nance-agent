import unittest

from f1nance.quant.backtest import backtest_weights, walk_forward


class BacktestWeightsTest(unittest.TestCase):
    def test_basic_equity_curve(self):
        r = backtest_weights(
            [{"A": 1.0}, {"A": 1.0}],
            {"A": [0.1, 0.1]},
        )
        self.assertEqual(r.n_periods, 2)
        self.assertAlmostEqual(r.equity_curve[0], 1.0, places=9)
        self.assertAlmostEqual(r.equity_curve[1], 1.1, places=9)
        self.assertAlmostEqual(r.equity_curve[2], 1.21, places=9)
        self.assertAlmostEqual(r.total_return, 0.21, places=9)
        self.assertEqual(r.turnover, [1.0, 0.0])  # initial deployment then hold
        self.assertAlmostEqual(r.mean_turnover, 0.5, places=9)
        self.assertAlmostEqual(r.hit_rate, 1.0, places=9)
        self.assertFalse(r.lookahead)

    def test_costs_reduce_return(self):
        # cost 100 bps/unit turnover: period 0 pays 1.0 * 0.01 = 0.01
        r = backtest_weights(
            [{"A": 1.0}, {"A": 1.0}],
            {"A": [0.1, 0.1]},
            cost_bps=100.0,
        )
        self.assertAlmostEqual(r.equity_curve[1], 1.09, places=9)   # 0.1 - 0.01
        self.assertAlmostEqual(r.equity_curve[2], 1.09 * 1.1, places=9)
        self.assertAlmostEqual(r.total_return, 1.09 * 1.1 - 1.0, places=9)
        self.assertAlmostEqual(r.total_cost, 0.01, places=9)

    def test_turnover_between_weights(self):
        # flip A -> B: turnover |0.5-1| + |0.5-0| = 1.0 in the second period
        r = backtest_weights(
            [{"A": 1.0, "B": 0.0}, {"A": 0.5, "B": 0.5}],
            {"A": [0.1, 0.1], "B": [0.0, 0.0]},
        )
        self.assertEqual(r.turnover, [1.0, 1.0])

    def test_weights_must_sum_to_one(self):
        with self.assertRaises(ValueError):
            backtest_weights([{"A": 0.5}], {"A": [0.1]})

    def test_held_asset_missing_return_raises(self):
        with self.assertRaises(ValueError):
            backtest_weights([{"B": 1.0}], {"A": [0.1]})

    def test_mismatched_series_lengths_raise(self):
        with self.assertRaises(ValueError):
            backtest_weights([{"A": 1.0}, {"A": 1.0}], {"A": [0.1, 0.2], "B": [0.1]})

    def test_weights_period_count_mismatch_raises(self):
        with self.assertRaises(ValueError):
            backtest_weights([{"A": 1.0}], {"A": [0.1, 0.2]})

    def test_negative_costs_raise(self):
        with self.assertRaises(ValueError):
            backtest_weights([{"A": 1.0}], {"A": [0.1]}, cost_bps=-1.0)


class WalkForwardTest(unittest.TestCase):
    def test_constant_predictor(self):
        history = {"A": [0.1, 0.1, 0.1, 0.1], "B": [0.0, 0.0, 0.0, 0.0]}
        result = walk_forward(history, lambda h: {"A": 0.5, "B": 0.5}, min_train=2)
        self.assertEqual(result.out_of_sample.n_periods, 2)
        # each period returns 0.5 * 0.1 = 0.05
        self.assertAlmostEqual(result.out_of_sample.equity_curve[1], 1.05, places=9)
        self.assertAlmostEqual(result.out_of_sample.equity_curve[2], 1.05 ** 2, places=9)
        self.assertFalse(result.out_of_sample.lookahead)
        self.assertTrue(result.in_sample.lookahead)
        self.assertEqual(result.in_sample.n_periods, 4)
        self.assertEqual(result.n_forecasts, 2)

    def test_point_in_time_guard(self):
        # predictor longs A if A's LAST available return was positive, else B.
        # If the harness leaked the current period's return, t=2 would see
        # A=+0.1 and go long A; it must instead see only A[-1] = -0.1 -> B.
        history = {"A": [0.1, -0.1, 0.1, -0.1], "B": [-0.1, 0.1, -0.1, 0.1]}

        def predictor(h):
            return {"A": 1.0, "B": 0.0} if h["A"][-1] > 0 else {"A": 0.0, "B": 1.0}

        result = walk_forward(history, predictor, min_train=2)
        # t=2 -> B (period return -0.1); t=3 -> A (period return -0.1)
        self.assertEqual(result.out_of_sample.n_periods, 2)
        self.assertAlmostEqual(result.out_of_sample.equity_curve[1], 0.9, places=9)
        self.assertAlmostEqual(result.out_of_sample.equity_curve[2], 0.81, places=9)

    def test_in_sample_uses_full_history(self):
        history = {"A": [0.1, -0.1, 0.1, -0.1], "B": [-0.1, 0.1, -0.1, 0.1]}

        def predictor(h):
            return {"A": 1.0, "B": 0.0} if h["A"][-1] > 0 else {"A": 0.0, "B": 1.0}

        result = walk_forward(history, predictor, min_train=2)
        # in-sample sees the full series: A[-1] = -0.1 -> constant B
        # B returns = [-0.1, 0.1, -0.1, 0.1] -> equity 1, .9, .99, .891, .9801
        self.assertTrue(result.in_sample.lookahead)
        self.assertAlmostEqual(result.in_sample.equity_curve[-1], 0.9801, places=9)

    def test_rolling_window_limits_training_data(self):
        history = {"A": [0.1, 0.1, 0.1, 0.1, 0.1]}
        seen_lengths = []

        def predictor(h):
            seen_lengths.append(len(h["A"]))
            return {"A": 1.0}

        walk_forward(history, predictor, min_train=3, window=2)
        # rolling window of 2: each out-of-sample training slice is exactly 2
        # observations (the in-sample baseline calls follow with the full series)
        self.assertEqual(seen_lengths[:2], [2, 2])

    def test_min_train_too_large_raises(self):
        history = {"A": [0.1, 0.1, 0.1]}
        with self.assertRaises(ValueError):
            walk_forward(history, lambda h: {"A": 1.0}, min_train=3)

    def test_min_train_too_small_raises(self):
        history = {"A": [0.1, 0.1, 0.1]}
        with self.assertRaises(ValueError):
            walk_forward(history, lambda h: {"A": 1.0}, min_train=1)

    def test_predictor_weights_must_sum_to_one(self):
        history = {"A": [0.1, 0.1, 0.1], "B": [0.0, 0.0, 0.0]}
        with self.assertRaises(ValueError):
            walk_forward(history, lambda h: {"A": 0.6, "B": 0.6}, min_train=2)


if __name__ == "__main__":
    unittest.main()
