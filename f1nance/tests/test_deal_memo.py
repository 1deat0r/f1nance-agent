import unittest

from f1nance.deal_memo import build_deal_memo


# A consistent reference deal (the same cost_synergies feeds accretion and
# synergy value — one synergy number, one deal). Acquirer $500 NI / 100 sh
# (EPS $5.00), $120 target NI, $2,000 deal 50/50 cash/stock at a $50 price
# (20 new shares), $100 pre-tax cost synergies, 5% debt on the $1,000 cash,
# 25% tax, 10% discount, 2-year ramp, $400 premium, $50 integration costs.
MERGER = dict(
    acquirer_ni=500.0,
    acquirer_shares=100.0,
    target_ni=120.0,
    purchase_price=2000.0,
    cash_portion=1000.0,
    stock_portion=1000.0,
    acquirer_share_price=50.0,
    tax_rate=0.25,
    cost_synergies=100.0,
    new_debt_rate=0.05,
    discount_rate=0.10,
    ramp_years=2,
    premium_paid=400.0,
    integration_costs=50.0,
)

LBO = dict(
    enterprise_value=1000.0,
    existing_net_debt=200.0,
    fees=30.0,
    entry_debt=700.0,
    ebitda_0=100.0,
    ebitda_growth=0.05,
    years=5,
    fcf_margin=0.60,
    exit_multiple=8.0,
    interest_rate=0.06,
    tax_rate=0.25,
)

RISK = dict(
    nav=30520.0,
    metrics={"gross_exposure": 1.20},
    limits=[{"name": "gross exposure", "metric": "gross_exposure",
             "threshold": 1.50, "direction": "max"}],
    exposures={"equity": 20000.0, "rates": -5000.0},
    scenarios=[{"name": "equity -30%", "shocks": {"equity": -0.30}}],
    loss_budget=5000.0,
)


class MergerMemoTest(unittest.TestCase):
    def test_favorable_reference(self):
        memo = build_deal_memo({"merger": dict(MERGER)})
        self.assertEqual(memo.recommendation, "favorable")
        # pro-forma NI = 500 + 120 + 100*0.75 - (1000*0.05)*0.75 = 657.5 over 120 sh
        self.assertAlmostEqual(memo.accretion.pro_forma_eps, 657.5 / 120.0)
        self.assertAlmostEqual(memo.accretion.accretion_pct, 0.095833, places=6)
        self.assertTrue(memo.accretion.accretive)
        # net synergy value = 75 * 9.5454545 - 450 = 265.9, covered
        self.assertAlmostEqual(memo.synergy.net_value, 265.909, places=3)
        self.assertTrue(memo.synergy.covered)
        # break-even run-rate = (400 + 50) / 9.5454545 / 0.75 = 62.857
        self.assertAlmostEqual(memo.breakeven.required_cost_synergies, 62.857, places=3)

    def test_scorecard_is_pass_pass(self):
        memo = build_deal_memo({"merger": dict(MERGER)})
        verdicts = {c.name: c.verdict for c in memo.checks}
        self.assertEqual(verdicts, {"accretion": "pass", "synergy coverage": "pass"})

    def test_dilutive_uncovered_is_adverse(self):
        bad = dict(MERGER, cost_synergies=0.0)
        memo = build_deal_memo({"merger": bad})
        self.assertEqual(memo.recommendation, "adverse")
        self.assertFalse(memo.accretion.accretive)
        self.assertFalse(memo.synergy.covered)
        names = [c.name for c in memo.checks if c.verdict == "fail"]
        self.assertEqual(names, ["accretion", "synergy coverage"])
        self.assertTrue(any("diluted" in lc for lc in memo.loss_cases))

    def test_falsify_names_the_synergy_assumption(self):
        memo = build_deal_memo({"merger": dict(MERGER)})
        self.assertIn("synergy", memo.falsify)
        self.assertIn("run-rate", memo.falsify)

    def test_missing_premium_recorded_not_computed(self):
        bad = {k: v for k, v in MERGER.items() if k != "premium_paid"}
        memo = build_deal_memo({"merger": bad})
        self.assertIn("merger", memo.not_computed)
        self.assertIn("premium_paid", memo.not_computed["merger"])
        self.assertIsNone(memo.accretion)
        self.assertEqual(memo.recommendation, "inconclusive")


class LboMemoTest(unittest.TestCase):
    def test_meets_hurdle(self):
        memo = build_deal_memo({"lbo": dict(LBO, hurdle_irr=0.09)})
        self.assertAlmostEqual(memo.lbo.moic, 1.599858, places=4)
        self.assertAlmostEqual(memo.lbo.irr, 0.09856, places=4)
        self.assertEqual(memo.recommendation, "favorable")

    def test_below_hurdle_is_adverse(self):
        memo = build_deal_memo({"lbo": dict(LBO, hurdle_irr=0.15)})
        self.assertEqual(memo.recommendation, "adverse")
        self.assertEqual(
            [c.name for c in memo.checks if c.verdict == "fail"], ["sponsor return"])

    def test_no_hurdle_is_inconclusive(self):
        memo = build_deal_memo({"lbo": dict(LBO)})
        self.assertEqual(memo.recommendation, "inconclusive")
        self.assertEqual(
            [c.verdict for c in memo.checks if c.name == "sponsor return"], ["skip"])

    def test_falsify_names_the_exit_multiple(self):
        memo = build_deal_memo({"lbo": dict(LBO, hurdle_irr=0.09)})
        self.assertIn("exit multiple", memo.falsify)


class RiskMemoTest(unittest.TestCase):
    def test_limits_pass(self):
        memo = build_deal_memo({"risk": {k: v for k, v in RISK.items()
                                        if k not in ("exposures", "scenarios", "loss_budget", "nav")}})
        self.assertAlmostEqual(memo.limits.worst.utilization, 1.20 / 1.50)
        self.assertEqual(memo.recommendation, "favorable")

    def test_limits_breach_is_adverse(self):
        risk = {k: v for k, v in RISK.items()
                if k not in ("exposures", "scenarios", "loss_budget", "nav")}
        risk["limits"] = [{"name": "gross exposure", "metric": "gross_exposure",
                           "threshold": 1.0}]
        memo = build_deal_memo({"risk": risk})
        self.assertEqual(memo.recommendation, "adverse")
        self.assertEqual(memo.limits.breach_count, 1)

    def test_stress_budget_fail(self):
        memo = build_deal_memo({"risk": RISK})
        # equity -30% on a $20,000 exposure = -$6,000, beyond the $5,000 budget
        self.assertAlmostEqual(memo.stress[0].pnl, -6000.0)
        self.assertEqual(memo.recommendation, "adverse")

    def test_stress_budget_pass(self):
        memo = build_deal_memo({"risk": dict(RISK, loss_budget=10000.0)})
        self.assertEqual(memo.recommendation, "favorable")

    def test_stress_without_budget_is_inconclusive(self):
        risk = {k: v for k, v in RISK.items() if k != "loss_budget"}
        memo = build_deal_memo({"risk": risk})
        self.assertEqual(memo.recommendation, "inconclusive")

    def test_headline_stress_loss_is_first(self):
        memo = build_deal_memo({"risk": RISK})
        self.assertIn("equity -30%", memo.loss_cases[0])

    def test_risk_block_without_subblocks_not_computed(self):
        memo = build_deal_memo({"risk": {}})
        self.assertIn("risk", memo.not_computed)
        self.assertEqual(memo.recommendation, "inconclusive")


class FullMemoTest(unittest.TestCase):
    def test_adverse_when_stress_breaches_even_if_merger_favorable(self):
        memo = build_deal_memo({"merger": dict(MERGER), "risk": dict(RISK)})
        self.assertEqual(memo.recommendation, "adverse")
        verdicts = {c.name: c.verdict for c in memo.checks}
        self.assertEqual(verdicts["accretion"], "pass")
        self.assertEqual(verdicts["synergy coverage"], "pass")
        self.assertEqual(verdicts["stress budget"], "fail")

    def test_full_favorable(self):
        spec = {"merger": dict(MERGER), "lbo": dict(LBO, hurdle_irr=0.09),
                "risk": dict(RISK, loss_budget=10000.0)}
        memo = build_deal_memo(spec)
        self.assertEqual(memo.recommendation, "favorable")
        self.assertEqual(len([c for c in memo.checks if c.verdict == "fail"]), 0)

    def test_metadata_and_override(self):
        memo = build_deal_memo({
            "deal_id": "acme-buys-beta",
            "names": {"acquirer": "Acme", "target": "Beta"},
            "merger": dict(MERGER),
            "falsify": "overridden condition",
            "loss_cases": ["extra case"],
        })
        self.assertEqual(memo.deal_id, "acme-buys-beta")
        self.assertEqual(memo.acquirer, "Acme")
        self.assertEqual(memo.target, "Beta")
        self.assertEqual(memo.falsify, "overridden condition")
        self.assertIn("extra case", memo.loss_cases)


class DegenerateTest(unittest.TestCase):
    def test_empty_spec_raises(self):
        with self.assertRaises(ValueError):
            build_deal_memo({})

    def test_unbalanced_merger_recorded_not_computed(self):
        bad = dict(MERGER, cash_portion=900.0, stock_portion=900.0)
        memo = build_deal_memo({"merger": bad})
        self.assertIn("merger", memo.not_computed)
        self.assertIn("purchase_price", memo.not_computed["merger"])
        self.assertEqual(memo.recommendation, "inconclusive")

    def test_over_levered_lbo_recorded_not_computed(self):
        bad = dict(LBO, entry_debt=1100.0)
        memo = build_deal_memo({"lbo": bad})
        self.assertIn("lbo", memo.not_computed)
        self.assertEqual(memo.recommendation, "inconclusive")

    def test_limit_on_missing_metric_recorded_not_computed(self):
        risk = dict(RISK, metrics={"other": 1.0})
        memo = build_deal_memo({"risk": risk})
        self.assertIn("risk", memo.not_computed)


if __name__ == "__main__":
    unittest.main()
