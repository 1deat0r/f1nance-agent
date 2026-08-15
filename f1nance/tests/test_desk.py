import unittest

from f1nance.desk import (
    DESK_SEATS,
    ROSTER_ORDER,
    STANCES,
    Brief,
    Desk,
    Finding,
    Seat,
    aggregate,
    get_seat,
    route,
    scripted_executor,
)


def finding(seat, stance="bullish", confidence=0.6, **kw):
    defaults = dict(
        thesis=f"{seat} sees upside",
        stance=stance,
        confidence=confidence,
        loss_case="the thesis breaks and ~-10%",
        falsify="price below support",
    )
    defaults.update(kw)
    defaults["seat"] = seat
    return Finding(**defaults)


class RosterTest(unittest.TestCase):
    def test_five_seats_in_roster_order(self):
        self.assertEqual(tuple(DESK_SEATS), ROSTER_ORDER)
        self.assertEqual(len(DESK_SEATS), 5)

    def test_every_seat_has_required_fields(self):
        for seat in DESK_SEATS.values():
            self.assertIsInstance(seat, Seat)
            self.assertTrue(seat.label)
            self.assertTrue(seat.domain)
            self.assertTrue(seat.roles)
            self.assertTrue(seat.engines)
            self.assertTrue(seat.keywords)
            self.assertTrue(seat.mandate)

    def test_get_seat_case_insensitive(self):
        self.assertEqual(get_seat("PM").name, "pm")
        self.assertEqual(get_seat(" Cfo ").name, "cfo")

    def test_get_seat_unknown_raises(self):
        with self.assertRaises(ValueError):
            get_seat("intern")


class RouteTest(unittest.TestCase):
    def test_keyword_routes_single_seat(self):
        self.assertEqual([s.name for s in route("rebalance the portfolio")], ["pm"])
        self.assertEqual([s.name for s in route("backtest a momentum factor")], ["quant"])
        self.assertEqual([s.name for s in route("execute a limit order")], ["trader"])
        self.assertEqual([s.name for s in route("valuation of a merger target")], ["banker"])
        self.assertEqual([s.name for s in route("forecast the cash budget")], ["cfo"])

    def test_keyword_routes_multiple_seats(self):
        names = [s.name for s in route("trade the position with a sizing check")]
        self.assertIn("pm", names)
        self.assertIn("trader", names)

    def test_explicit_seats_select_exactly(self):
        names = [s.name for s in route("x", explicit=("trader", "pm"))]
        self.assertEqual(names, ["pm", "trader"])  # roster order, not given order

    def test_explicit_seat_unknown_raises(self):
        with self.assertRaises(ValueError):
            route("x", explicit=("pm", "nobody"))

    def test_unrouteable_raises(self):
        with self.assertRaises(ValueError):
            route("flibbertigibbet")


class BriefTest(unittest.TestCase):
    def test_blank_objective_raises(self):
        with self.assertRaises(ValueError):
            Brief("   ")

    def test_constraints_and_seats_coerced_to_tuple(self):
        b = Brief("x", constraints=["a"], seats=["pm"])
        self.assertIsInstance(b.constraints, tuple)
        self.assertIsInstance(b.seats, tuple)

    def test_defaults(self):
        b = Brief("x")
        self.assertEqual(b.context, "")
        self.assertEqual(b.horizon, "")
        self.assertEqual(b.risk_capacity, "")
        self.assertEqual(b.constraints, ())
        self.assertEqual(b.seats, ())


class FindingTest(unittest.TestCase):
    def test_valid_finding(self):
        f = finding("pm")
        self.assertEqual(f.seat, "pm")
        self.assertEqual(f.stance, "bullish")

    def test_blank_thesis_raises(self):
        with self.assertRaises(ValueError):
            finding("pm", thesis="")

    def test_unknown_stance_raises(self):
        with self.assertRaises(ValueError):
            finding("pm", stance="euphoric")

    def test_confidence_below_zero_raises(self):
        with self.assertRaises(ValueError):
            finding("pm", confidence=-0.1)

    def test_confidence_above_one_raises(self):
        with self.assertRaises(ValueError):
            finding("pm", confidence=1.5)

    def test_missing_loss_case_raises(self):
        with self.assertRaises(ValueError):
            finding("pm", loss_case="")

    def test_missing_falsify_raises(self):
        with self.assertRaises(ValueError):
            finding("pm", falsify="")

    def test_actions_coerced_to_tuple(self):
        f = finding("pm", actions=["trim to 15%"])
        self.assertEqual(f.actions, ("trim to 15%",))


class AggregateTest(unittest.TestCase):
    def _brief(self):
        return Brief("test")

    def test_unanimous(self):
        v = aggregate(self._brief(), [finding("pm"), finding("trader")])
        self.assertEqual(v.stance, "bullish")
        self.assertEqual(v.agreement, 1.0)
        self.assertEqual(v.dissent, ())

    def test_majority_with_dissent(self):
        v = aggregate(
            self._brief(),
            [finding("pm", "bullish"), finding("trader", "bullish"),
             finding("quant", "bearish")],
        )
        self.assertEqual(v.stance, "bullish")
        self.assertAlmostEqual(v.agreement, 2 / 3)
        self.assertEqual(v.dissent, ("quant",))

    def test_tie_is_mixed(self):
        v = aggregate(self._brief(), [finding("pm", "bullish"), finding("trader", "bearish")])
        self.assertEqual(v.stance, "mixed")
        self.assertAlmostEqual(v.agreement, 0.5)
        self.assertEqual(v.dissent, ())

    def test_confidence_is_mean(self):
        v = aggregate(self._brief(), [finding("pm", confidence=0.8), finding("trader", confidence=0.4)])
        self.assertAlmostEqual(v.confidence, 0.6)

    def test_loss_cases_survive_aggregation(self):
        v = aggregate(self._brief(), [finding("pm", loss_case="case A"), finding("trader", loss_case="case B")])
        self.assertEqual(v.loss_cases, {"pm": "case A", "trader": "case B"})

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            aggregate(self._brief(), [])


class DeskRunTest(unittest.TestCase):
    def _brief(self, **kw):
        defaults = dict(objective="size the AAPL position", seats=("pm", "trader"))
        defaults.update(kw)
        return Brief(**defaults)

    def _findings(self):
        return {
            "pm": {"thesis": "t", "stance": "bullish", "confidence": 0.7,
                   "loss_case": "l", "falsify": "f"},
            "trader": {"thesis": "t", "stance": "neutral", "confidence": 0.5,
                       "loss_case": "l", "falsify": "f"},
        }

    def test_run_returns_verdict(self):
        v = Desk().run(self._brief(), scripted_executor(self._findings()))
        self.assertEqual(v.seats, ("pm", "trader"))
        self.assertEqual(v.stance, "mixed")  # one bullish, one neutral -> no majority? (1-1 tie)
        self.assertAlmostEqual(v.confidence, 0.6)

    def test_missing_scripted_finding_raises(self):
        findings = {"pm": self._findings()["pm"]}
        with self.assertRaises(ValueError):
            Desk().run(self._brief(), scripted_executor(findings))

    def test_executor_returning_none_raises(self):
        with self.assertRaises(ValueError):
            Desk().run(self._brief(), lambda seat, brief: None)

    def test_executor_returning_non_finding_raises(self):
        with self.assertRaises(TypeError):
            Desk().run(self._brief(), lambda seat, brief: "not a finding")

    def test_mismatched_seat_raises(self):
        def wrong_seat(seat, brief):
            return finding("pm")
        with self.assertRaises(ValueError):
            Desk().run(self._brief(seats=("trader",)), wrong_seat)

    def test_custom_desk_routes_against_own_roster(self):
        desk = Desk(seats={"pm": DESK_SEATS["pm"]})
        with self.assertRaises(ValueError):
            desk.route(Brief("backtest a factor"))  # quant not in this desk


if __name__ == "__main__":
    unittest.main()
