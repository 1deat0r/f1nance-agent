"""The desk's task and output models — ``Brief``, ``Finding``, ``Verdict``.

A task enters the desk as a ``Brief``. Each seated specialist returns a
``Finding`` — a thesis with a stance, a confidence, a loss case, and a
falsification condition. The coordinator folds the findings into a
``Verdict`` — the desk's single answer — where consensus and dissent are
surfaced and every loss case survives aggregation.

Every model is a frozen dataclass with structural validation in
``__post_init__``: a malformed brief or finding raises rather than being
smoothed over. This is the same no-fabrication discipline as the rest of
``f1nance``: a view without a loss case, or a confidence outside [0, 1], is
an error — not a data point.
"""

from __future__ import annotations

from dataclasses import dataclass

STANCES = ("bullish", "bearish", "neutral")


def _clean(value) -> str:
    return (value or "").strip()


@dataclass(frozen=True)
class Brief:
    """A task handed to the desk.

    ``seats`` is an explicit seat selection; when empty, the objective is
    routed by keyword. ``horizon`` and ``risk_capacity`` are suitability
    inputs for the executor/umbrella — the deterministic coordinator carries
    them but does not reason over them.
    """

    objective: str
    context: str = ""
    horizon: str = ""
    risk_capacity: str = ""
    constraints: tuple = ()
    seats: tuple = ()

    def __post_init__(self):
        if not _clean(self.objective):
            raise ValueError("a brief needs an objective")
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "seats", tuple(self.seats))


@dataclass(frozen=True)
class Finding:
    """One seat's answer to a brief.

    The guardrail fields are mandatory: a view without a ``loss_case`` (risk
    before return) or a ``falsify`` condition is invalid, and ``confidence``
    must be in [0, 1].
    """

    seat: str
    thesis: str
    stance: str            # one of STANCES
    confidence: float      # 0..1
    loss_case: str
    falsify: str
    actions: tuple = ()

    def __post_init__(self):
        if not _clean(self.thesis):
            raise ValueError(f"seat {self.seat!r}: a finding needs a thesis")
        if self.stance not in STANCES:
            raise ValueError(
                f"seat {self.seat!r}: stance must be one of {STANCES}, "
                f"got {self.stance!r}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"seat {self.seat!r}: confidence must be in [0, 1], "
                f"got {self.confidence!r}"
            )
        if not _clean(self.loss_case):
            raise ValueError(
                f"seat {self.seat!r}: a finding needs a loss case "
                "(risk before return)"
            )
        if not _clean(self.falsify):
            raise ValueError(
                f"seat {self.seat!r}: a finding needs a falsification condition"
            )
        object.__setattr__(self, "actions", tuple(self.actions))


@dataclass(frozen=True)
class Verdict:
    """The desk's single answer, folded from the seated seats' findings."""

    brief: Brief
    findings: tuple        # one per seated seat, in roster order
    stance: str            # plurality stance, or "mixed" on a tie
    agreement: float       # fraction of seats holding the plurality stance
    dissent: tuple         # seat names disagreeing with the plurality stance
    confidence: float      # mean confidence across the seated seats

    @property
    def seats(self) -> tuple:
        return tuple(f.seat for f in self.findings)

    @property
    def loss_cases(self) -> dict:
        """Every seat's loss case, keyed by seat — aggregation never drops one."""
        return {f.seat: f.loss_case for f in self.findings}

    @property
    def falsify_conditions(self) -> dict:
        return {f.seat: f.falsify for f in self.findings}


def aggregate(brief: Brief, findings: list) -> Verdict:
    """Fold findings into a verdict.

    ``stance`` is the plurality stance (unique leader), or ``"mixed"`` on a
    tie. ``agreement`` is the largest bloc as a fraction of the seats seated.
    ``dissent`` lists every seat that does not hold the plurality stance (it
    is empty when the stance is ``"mixed"`` — there is no single majority to
    dissent from). ``confidence`` is the plain mean across seats; dissent is
    reported *alongside* it, not silently averaged away.
    """
    fs = tuple(findings)
    if not fs:
        raise ValueError("cannot aggregate an empty desk")

    counts = {s: 0 for s in STANCES}
    for f in fs:
        counts[f.stance] += 1

    max_n = max(counts.values())
    leaders = [s for s in STANCES if counts[s] == max_n]
    stance = leaders[0] if len(leaders) == 1 else "mixed"

    n = len(fs)
    agreement = max_n / n
    dissent = () if stance == "mixed" else tuple(
        f.seat for f in fs if f.stance != stance
    )
    confidence = sum(f.confidence for f in fs) / n

    return Verdict(
        brief=brief,
        findings=fs,
        stance=stance,
        agreement=agreement,
        dissent=dissent,
        confidence=confidence,
    )
