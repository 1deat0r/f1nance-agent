"""Append-only compliance ledger — the F1NANCE audit trail.

Every decision is mirrored exactly once, with its rationale, confidence, and
loss case. Nothing is edited or deleted: status changes (fills, cancels) are
appended as events, and the current status of any decision is *derived* by
folding the event stream rather than by mutating the record. A decision that
fails a compliance rule is recorded as ``rejected`` (with its violations), not
silently dropped — an attempted bad trade is still part of the trail, and a
rejected decision cannot subsequently be filled.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Callable, Optional


# --------------------------------------------------------------------------
# Confidence scale (numeric is canonical; high/medium/low are display labels)
# --------------------------------------------------------------------------

CONFIDENCE_LABELS = {"high": 0.8, "medium": 0.5, "low": 0.2}


def parse_confidence(value) -> float:
    """Normalize a confidence to a float.

    Accepts a number (kept as-is; range is enforced by the compliance rule
    ``confidence_in_range``, not here) or the label ``high``/``medium``/``low``
    (case-insensitive).
    """
    if isinstance(value, str):
        v = value.strip()
        key = v.lower()
        if key in CONFIDENCE_LABELS:
            return CONFIDENCE_LABELS[key]
        try:
            return float(v)
        except ValueError:
            raise ValueError(
                f"confidence {value!r} is not a number or a known label "
                f"(high/medium/low)"
            ) from None
    return float(value)


def confidence_label(confidence: float) -> str:
    """Map a numeric confidence to the high/medium/low display label."""
    if confidence >= 0.7:
        return "high"
    if confidence >= 0.4:
        return "medium"
    return "low"


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Decision:
    """A single trading decision, as entered into the audit trail."""

    instrument: str
    side: str                 # "buy" | "sell"
    quantity: float
    order_type: str           # "market" | "limit" | "stop" | "stop_limit"
    rationale: str
    confidence: float
    risk: str                 # the loss case
    falsify: str              # what would prove the view wrong
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    reference_price: Optional[float] = None
    meta: dict = field(default_factory=dict)
    # filled by Ledger.record()
    decision_id: str = ""
    seq: int = 0
    timestamp: str = ""
    status: str = "pending"
    violations: tuple = ()


@dataclass(frozen=True)
class Event:
    """An immutable post-decision event (fill / partial_fill / cancel)."""

    seq: int
    decision_id: str
    kind: str
    timestamp: str
    price: Optional[float] = None
    quantity: Optional[float] = None


# --------------------------------------------------------------------------
# Compliance rules
# --------------------------------------------------------------------------

Rule = Callable[[Decision], Optional[str]]


def has_instrument(d: Decision) -> Optional[str]:
    return None if (d.instrument or "").strip() else "missing instrument"


def has_rationale(d: Decision) -> Optional[str]:
    return None if (d.rationale or "").strip() else "missing rationale"


def has_risk(d: Decision) -> Optional[str]:
    return None if (d.risk or "").strip() else "missing loss case"


def has_falsify(d: Decision) -> Optional[str]:
    return None if (d.falsify or "").strip() else "missing falsification condition"


def confidence_in_range(d: Decision) -> Optional[str]:
    return None if 0.0 <= d.confidence <= 1.0 else "confidence out of range [0, 1]"


def positive_quantity(d: Decision) -> Optional[str]:
    return None if d.quantity > 0 else "non-positive quantity"


def known_order_type(d: Decision) -> Optional[str]:
    valid = {"market", "limit", "stop", "stop_limit"}
    return None if d.order_type in valid else f"unknown order type {d.order_type!r}"


def rule_max_notional(cap: float) -> Rule:
    """Reject a decision whose notional (quantity × reference_price) exceeds cap.

    Skipped (passes) when the decision has no ``reference_price``, since the
    notional cannot be sized without a price.
    """
    if cap < 0:
        raise ValueError("notional cap must be non-negative")

    def rule(d: Decision) -> Optional[str]:
        if d.reference_price is None:
            return None
        notional = d.quantity * d.reference_price
        if notional > cap:
            return f"notional {notional:.2f} exceeds cap {cap:.2f}"
        return None

    return rule


DEFAULT_RULES: list = [
    has_instrument,
    has_rationale,
    has_risk,
    has_falsify,
    confidence_in_range,
    positive_quantity,
    known_order_type,
]


class ComplianceEngine:
    """Runs a list of rules over a decision and returns the violations."""

    def __init__(self, rules: Optional[list] = None):
        self.rules = list(rules if rules is not None else DEFAULT_RULES)

    def check(self, decision: Decision) -> list:
        return [v for rule in self.rules if (v := rule(decision))]


# --------------------------------------------------------------------------
# The ledger
# --------------------------------------------------------------------------

class Ledger:
    """An append-only decision + event journal.

    ``record`` appends an immutable ``Decision`` (assigning id/seq/timestamp
    and a derived ``pending``/``rejected`` status). Fills and cancels are
    appended as ``Event`` records; the status of a decision is always derived
    from the event stream, never overwritten. A rejected decision refuses to
    be filled — the compliance gate is enforced at the ledger boundary.
    """

    def __init__(self, rules: Optional[list] = None, clock: Optional[Callable] = None):
        self.compliance = ComplianceEngine(rules)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._seq = 0
        self._records: list = []
        self._events: list = []

    # -- internals ---------------------------------------------------------

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _stamp(self) -> str:
        return self._clock().isoformat()

    def _require(self, decision_id: str) -> Decision:
        for r in self._records:
            if r.decision_id == decision_id:
                return r
        raise KeyError(f"unknown decision {decision_id!r}")

    def _append_event(self, decision_id: str, kind: str,
                      price: Optional[float] = None,
                      quantity: Optional[float] = None) -> Event:
        d = self._require(decision_id)
        if d.status == "rejected":
            raise ValueError(
                f"decision {decision_id!r} was rejected: {', '.join(d.violations)}"
            )
        if kind in ("fill", "partial_fill"):
            if price is None or price <= 0:
                raise ValueError("fill requires a positive price")
            if quantity is None or quantity <= 0:
                raise ValueError("fill requires a positive quantity")
        current = self.status_of(decision_id)
        if current == "cancelled":
            raise ValueError(f"decision {decision_id!r} is already cancelled")
        if current == "filled":
            raise ValueError(f"decision {decision_id!r} is already filled")
        ev = Event(self._next_seq(), decision_id, kind, self._stamp(), price, quantity)
        self._events.append(ev)
        return ev

    # -- public API --------------------------------------------------------

    def record(self, decision: Decision) -> Decision:
        confidence = parse_confidence(decision.confidence)
        normalized = replace(decision, confidence=confidence)
        violations = self.compliance.check(normalized)
        seq = self._next_seq()
        final = replace(
            normalized,
            decision_id=f"D{seq:06d}",
            seq=seq,
            timestamp=self._stamp(),
            status="rejected" if violations else "pending",
            violations=tuple(violations),
        )
        self._records.append(final)
        return final

    def fill(self, decision_id: str, price: float, quantity: Optional[float] = None) -> Event:
        d = self._require(decision_id)
        return self._append_event(
            decision_id, "fill", price=price,
            quantity=quantity if quantity is not None else d.quantity,
        )

    def partial_fill(self, decision_id: str, price: float, quantity: float) -> Event:
        return self._append_event(decision_id, "partial_fill", price=price, quantity=quantity)

    def cancel(self, decision_id: str) -> Event:
        return self._append_event(decision_id, "cancel")

    def status_of(self, decision_id: str) -> str:
        d = self._require(decision_id)
        events = [e for e in self._events if e.decision_id == decision_id]
        if any(e.kind == "cancel" for e in events):
            return "cancelled"
        if any(e.kind == "fill" for e in events):
            return "filled"
        if any(e.kind == "partial_fill" for e in events):
            return "partially_filled"
        return d.status

    def fills_of(self, decision_id: str) -> list:
        self._require(decision_id)
        return [e for e in self._events
                if e.decision_id == decision_id and e.kind in ("fill", "partial_fill")]

    @property
    def records(self) -> tuple:
        return tuple(self._records)

    @property
    def events(self) -> tuple:
        return tuple(self._events)

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self):
        return iter(self._records)

    def export(self) -> dict:
        return {
            "decisions": [
                {
                    "decision_id": d.decision_id,
                    "seq": d.seq,
                    "timestamp": d.timestamp,
                    "instrument": d.instrument,
                    "side": d.side,
                    "quantity": d.quantity,
                    "order_type": d.order_type,
                    "limit_price": d.limit_price,
                    "stop_price": d.stop_price,
                    "reference_price": d.reference_price,
                    "rationale": d.rationale,
                    "confidence": d.confidence,
                    "confidence_label": confidence_label(d.confidence),
                    "risk": d.risk,
                    "falsify": d.falsify,
                    "status": self.status_of(d.decision_id),
                    "violations": list(d.violations),
                    "meta": d.meta,
                }
                for d in self._records
            ],
            "events": [
                {
                    "seq": e.seq,
                    "decision_id": e.decision_id,
                    "kind": e.kind,
                    "timestamp": e.timestamp,
                    "price": e.price,
                    "quantity": e.quantity,
                }
                for e in self._events
            ],
        }


# --------------------------------------------------------------------------
# Persistence (JSONL — append-only on disk)
# --------------------------------------------------------------------------

def save_ledger(ledger: Ledger, path) -> None:
    """Write a ledger to disk as JSONL (one record/event per line)."""
    with open(path, "w", encoding="utf-8") as fh:
        for d in ledger.records:
            fh.write(json.dumps({"type": "decision", **asdict(d)}, default=str) + "\n")
        for e in ledger.events:
            fh.write(json.dumps({"type": "event", **asdict(e)}, default=str) + "\n")


def _decision_from_dict(obj: dict) -> Decision:
    d = dict(obj)
    d.pop("type", None)
    d["violations"] = tuple(d.get("violations", []))
    return Decision(**d)


def _event_from_dict(obj: dict) -> Event:
    d = dict(obj)
    d.pop("type", None)
    return Event(**d)


def load_ledger(path) -> Ledger:
    """Load a JSONL ledger file back into an append-capable ``Ledger``."""
    ledger = Ledger()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            kind = obj.get("type")
            if kind == "decision":
                ledger._records.append(_decision_from_dict(obj))
                ledger._seq = max(ledger._seq, obj.get("seq", 0))
            elif kind == "event":
                ledger._events.append(_event_from_dict(obj))
                ledger._seq = max(ledger._seq, obj.get("seq", 0))
            else:
                raise ValueError(f"unrecognized ledger line type: {kind!r}")
    return ledger
