"""Scenario stress testing and reverse stress testing.

Hermes-independent, stdlib-only (``math`` + ``dataclasses``). A stress test is
a set of :class:`Scenario` shocks applied to a portfolio's *factor exposures*;
the result is the P&L under each scenario. A reverse stress test inverts the
question: given a target loss, what shock to a single factor produces it?

Conventions:

- ``exposures`` maps a factor (e.g. ``"equity"``, ``"rates"``, ``"fx"``,
  ``"credit"``) to the portfolio's net exposure to that factor, in portfolio
  currency. Negative exposure is a short.
- A :class:`Scenario` maps a factor to a **return shock** in decimal form
  (``-0.30`` = -30%). The scenario P&L is ``Σ exposure × shock`` — a linear,
  first-order stress. A shock on a factor the book has no exposure to
  contributes zero (honestly: the book does not hold that risk).
- **Reverse stress is linear and single-factor.** It solves
  ``shock = -target_loss / exposure`` — the shock that, applied to that factor
  alone, produces exactly ``target_loss``. Convexity (gamma, optionality) is
  not modeled; for an options book the honest tool is the derivatives engine's
  re-pricing under the shock, not this linear approximation.
- Degenerate input raises: an empty exposure map, no scenarios, a scenario
  that shocks nothing, a non-positive ``nav``, a non-positive ``target_loss``,
  or a zero-exposure factor in a reverse stress.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


@dataclass(frozen=True)
class Scenario:
    """A named set of factor shocks (decimal returns)."""

    name: str
    shocks: Dict[str, float]

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("a scenario needs a non-empty name")
        if not self.shocks:
            raise ValueError(f"scenario {self.name!r} shocks nothing")
        for key, value in self.shocks.items():
            if not str(key).strip():
                raise ValueError(f"scenario {self.name!r} has a blank factor")
            if not math.isfinite(float(value)):
                raise ValueError(f"scenario {self.name!r} factor {key!r} shock must be finite")


@dataclass
class StressOutcome:
    """The result of one scenario applied to the exposure map."""

    name: str
    pnl: float
    pnl_pct: Optional[float]
    worst: str
    contributions: Dict[str, float]


@dataclass
class ReverseStressResult:
    """The shock to one factor that produces a target loss."""

    factor: str
    exposure: float
    target_loss: float
    shock: float


def _clean_exposures(exposures: Dict[str, float]) -> Dict[str, float]:
    if not exposures:
        raise ValueError("cannot stress-test an empty exposure map")
    clean: Dict[str, float] = {}
    for key, value in exposures.items():
        if not str(key).strip():
            raise ValueError("blank factor in exposures")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"exposure for {key!r} must be finite")
        clean[str(key)] = value
    return clean


def stress_test(
    exposures: Dict[str, float],
    scenarios: Sequence[Scenario],
    nav: Optional[float] = None,
) -> List[StressOutcome]:
    """Apply each scenario to the exposures and report the P&L.

    ``nav`` enables ``pnl_pct`` (P&L as a fraction of NAV); when omitted the
    percentage is ``None``. A supplied ``nav`` must be positive.
    """
    clean = _clean_exposures(exposures)
    scenarios = list(scenarios)
    if not scenarios:
        raise ValueError("no scenarios supplied")
    if nav is not None:
        nav = float(nav)
        if nav <= 0:
            raise ValueError("nav must be positive")

    outcomes: List[StressOutcome] = []
    for scenario in scenarios:
        contributions: Dict[str, float] = {}
        pnl = 0.0
        for factor, exposure in clean.items():
            shock = float(scenario.shocks.get(factor, 0.0))
            contribution = exposure * shock
            contributions[factor] = contribution
            pnl += contribution
        worst = min(contributions, key=lambda f: contributions[f]) if contributions else ""
        outcomes.append(
            StressOutcome(
                name=scenario.name,
                pnl=pnl,
                pnl_pct=pnl / nav if nav is not None else None,
                worst=worst,
                contributions=contributions,
            )
        )
    return outcomes


def reverse_stress(
    exposures: Dict[str, float],
    factor: str,
    target_loss: float,
) -> ReverseStressResult:
    """Solve the single-factor shock that produces exactly ``target_loss``.

    ``target_loss`` is a positive magnitude (the loss we are stress-testing
    *toward*). The returned ``shock`` is signed correctly for the exposure:
    long exposure → negative shock, short exposure → positive shock.
    """
    clean = _clean_exposures(exposures)
    factor = str(factor)
    if factor not in clean:
        raise ValueError(f"unknown factor {factor!r}")
    exposure = clean[factor]
    if exposure == 0:
        raise ValueError(f"factor {factor!r} has zero exposure; cannot reverse-stress")
    target_loss = float(target_loss)
    if not math.isfinite(target_loss) or target_loss <= 0:
        raise ValueError("target_loss must be a positive number")
    return ReverseStressResult(
        factor=factor,
        exposure=exposure,
        target_loss=target_loss,
        shock=-target_loss / exposure,
    )
