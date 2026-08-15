import unittest

from f1nance.portfolio.attribution import brinson


class BrinsonTest(unittest.TestCase):
    PW = {"A": 0.7, "B": 0.3}
    BW = {"A": 0.6, "B": 0.4}
    PR = {"A": 0.12, "B": 0.03}
    BR = {"A": 0.10, "B": 0.05}

    def test_totals(self):
        r = brinson(self.PW, self.BW, self.PR, self.BR)
        self.assertAlmostEqual(r.portfolio_return, 0.093)
        self.assertAlmostEqual(r.benchmark_return, 0.08)
        self.assertAlmostEqual(r.active_return, 0.013)

    def test_effects(self):
        r = brinson(self.PW, self.BW, self.PR, self.BR)
        self.assertAlmostEqual(r.allocation_total, 0.005)
        self.assertAlmostEqual(r.selection_total, 0.004)
        self.assertAlmostEqual(r.interaction_total, 0.004)

    def test_effects_sum_to_active(self):
        r = brinson(self.PW, self.BW, self.PR, self.BR)
        total = r.allocation_total + r.selection_total + r.interaction_total
        self.assertAlmostEqual(total, r.active_return, places=9)

    def test_per_asset_rows(self):
        r = brinson(self.PW, self.BW, self.PR, self.BR)
        rows = {row.asset: row for row in r.rows}
        a = rows["A"]
        self.assertAlmostEqual(a.allocation_effect, 0.002)
        self.assertAlmostEqual(a.selection_effect, 0.012)
        self.assertAlmostEqual(a.interaction, 0.002)
        b = rows["B"]
        self.assertAlmostEqual(b.allocation_effect, 0.003)
        self.assertAlmostEqual(b.selection_effect, -0.008)
        self.assertAlmostEqual(b.interaction, 0.002)

    def test_identical_portfolio_has_zero_active(self):
        r = brinson(self.BW, self.BW, self.BR, self.BR)
        self.assertAlmostEqual(r.active_return, 0.0)
        self.assertAlmostEqual(r.allocation_total, 0.0)
        self.assertAlmostEqual(r.selection_total, 0.0)
        self.assertAlmostEqual(r.interaction_total, 0.0)

    def test_missing_return_treated_as_zero(self):
        # B present in weights but absent from returns -> return 0.0
        r = brinson({"A": 1.0}, {"A": 1.0}, {"A": 0.10}, {"A": 0.10})
        self.assertAlmostEqual(r.active_return, 0.0)

    def test_empty(self):
        r = brinson({}, {}, {}, {})
        self.assertEqual(r.rows, [])
        self.assertEqual(r.active_return, 0.0)


if __name__ == "__main__":
    unittest.main()
