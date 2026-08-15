import os
import tempfile
import unittest

from f1nance.execution.ledger import (
    Decision,
    Ledger,
    confidence_label,
    load_ledger,
    parse_confidence,
    rule_max_notional,
    save_ledger,
)


def decision(**kw):
    defaults = dict(
        instrument="AAPL", side="buy", quantity=100, order_type="market",
        rationale="momentum continuation", confidence=0.6,
        risk="break of the 50-day; ~-8%", falsify="close below the 200-day",
    )
    defaults.update(kw)
    return Decision(**defaults)


class RecordTest(unittest.TestCase):
    def test_record_assigns_identity(self):
        d = Ledger().record(decision())
        self.assertEqual(d.decision_id, "D000001")
        self.assertEqual(d.seq, 1)
        self.assertTrue(d.timestamp)
        self.assertEqual(d.status, "pending")
        self.assertEqual(d.violations, ())

    def test_sequence_increments(self):
        ledger = Ledger()
        ledger.record(decision())
        d2 = ledger.record(decision())
        self.assertEqual(d2.seq, 2)
        self.assertEqual(len(ledger), 2)

    def test_missing_rationale_rejected(self):
        d = Ledger().record(decision(rationale=""))
        self.assertEqual(d.status, "rejected")
        self.assertTrue(any("rationale" in v for v in d.violations))

    def test_missing_risk_rejected(self):
        d = Ledger().record(decision(risk=""))
        self.assertEqual(d.status, "rejected")

    def test_missing_falsify_rejected(self):
        d = Ledger().record(decision(falsify=""))
        self.assertEqual(d.status, "rejected")

    def test_confidence_out_of_range_rejected(self):
        d = Ledger().record(decision(confidence=1.5))
        self.assertEqual(d.status, "rejected")
        self.assertTrue(any("confidence" in v for v in d.violations))

    def test_confidence_label_accepted(self):
        d = Ledger().record(decision(confidence="high"))
        self.assertEqual(d.status, "pending")
        self.assertEqual(d.confidence, 0.8)

    def test_garbage_confidence_raises(self):
        with self.assertRaises(ValueError):
            Ledger().record(decision(confidence="giga"))

    def test_nonpositive_quantity_rejected(self):
        d = Ledger().record(decision(quantity=0))
        self.assertEqual(d.status, "rejected")

    def test_unknown_order_type_rejected(self):
        d = Ledger().record(decision(order_type="iceberg"))
        self.assertEqual(d.status, "rejected")

    def test_clean_decision_has_no_violations(self):
        d = Ledger().record(decision())
        self.assertEqual(d.violations, ())


class StatusTest(unittest.TestCase):
    def _ledger_with_decision(self):
        ledger = Ledger()
        d = ledger.record(decision())
        return ledger, d.decision_id

    def test_fill_sets_filled(self):
        ledger, did = self._ledger_with_decision()
        ledger.fill(did, price=190.0)
        self.assertEqual(ledger.status_of(did), "filled")

    def test_fill_defaults_quantity_to_order(self):
        ledger, did = self._ledger_with_decision()
        ev = ledger.fill(did, price=190.0)
        self.assertEqual(ev.quantity, 100)

    def test_partial_fill_sets_partially_filled(self):
        ledger, did = self._ledger_with_decision()
        ledger.partial_fill(did, price=190.0, quantity=40)
        self.assertEqual(ledger.status_of(did), "partially_filled")

    def test_partial_then_full(self):
        ledger, did = self._ledger_with_decision()
        ledger.partial_fill(did, price=190.0, quantity=40)
        ledger.fill(did, price=190.0)
        self.assertEqual(ledger.status_of(did), "filled")

    def test_cancel_sets_cancelled(self):
        ledger, did = self._ledger_with_decision()
        ledger.cancel(did)
        self.assertEqual(ledger.status_of(did), "cancelled")

    def test_fill_after_cancel_raises(self):
        ledger, did = self._ledger_with_decision()
        ledger.cancel(did)
        with self.assertRaises(ValueError):
            ledger.fill(did, price=190.0)

    def test_cancel_after_fill_raises(self):
        ledger, did = self._ledger_with_decision()
        ledger.fill(did, price=190.0)
        with self.assertRaises(ValueError):
            ledger.cancel(did)

    def test_fill_rejected_raises(self):
        ledger = Ledger()
        d = ledger.record(decision(rationale=""))
        with self.assertRaises(ValueError):
            ledger.fill(d.decision_id, price=190.0)

    def test_fill_unknown_raises(self):
        with self.assertRaises(KeyError):
            Ledger().fill("D000999", price=190.0)

    def test_fill_nonpositive_price_raises(self):
        ledger, did = self._ledger_with_decision()
        with self.assertRaises(ValueError):
            ledger.fill(did, price=0)


class ComplianceRuleTest(unittest.TestCase):
    def test_max_notional_rule(self):
        rule = rule_max_notional(10_000.0)
        d = decision(reference_price=200.0, quantity=100)  # notional 20000
        self.assertIsNotNone(rule(d))

    def test_max_notional_within_cap(self):
        rule = rule_max_notional(100_000.0)
        d = decision(reference_price=200.0, quantity=100)
        self.assertIsNone(rule(d))

    def test_max_notional_skips_without_reference_price(self):
        rule = rule_max_notional(1.0)
        self.assertIsNone(rule(decision(reference_price=None)))

    def test_max_notional_negative_cap_raises(self):
        with self.assertRaises(ValueError):
            rule_max_notional(-1.0)

    def test_custom_rules_replace_defaults(self):
        # a ledger with a single no-op rule only enforces that rule
        ledger = Ledger(rules=[lambda d: None])
        d = ledger.record(decision(rationale="", risk="", falsify="", quantity=0))
        self.assertEqual(d.status, "pending")


class PersistenceTest(unittest.TestCase):
    def test_roundtrip(self):
        ledger = Ledger()
        d = ledger.record(decision())
        ledger.fill(d.decision_id, price=190.0)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ledger.jsonl")
            save_ledger(ledger, path)
            loaded = load_ledger(path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded.status_of(d.decision_id), "filled")
        self.assertEqual(loaded.records[0].rationale, "momentum continuation")

    def test_loaded_ledger_continues_sequence(self):
        ledger = Ledger()
        ledger.record(decision())
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ledger.jsonl")
            save_ledger(ledger, path)
            loaded = load_ledger(path)
            d2 = loaded.record(decision())
        self.assertEqual(d2.seq, 2)


class ConfidenceTest(unittest.TestCase):
    def test_parse_labels(self):
        self.assertEqual(parse_confidence("high"), 0.8)
        self.assertEqual(parse_confidence("MEDIUM"), 0.5)
        self.assertEqual(parse_confidence("low"), 0.2)

    def test_parse_float(self):
        self.assertEqual(parse_confidence(0.63), 0.63)
        self.assertEqual(parse_confidence("0.63"), 0.63)

    def test_parse_unknown_label_raises(self):
        with self.assertRaises(ValueError):
            parse_confidence("certain")

    def test_confidence_label_mapping(self):
        self.assertEqual(confidence_label(0.8), "high")
        self.assertEqual(confidence_label(0.5), "medium")
        self.assertEqual(confidence_label(0.1), "low")


if __name__ == "__main__":
    unittest.main()
