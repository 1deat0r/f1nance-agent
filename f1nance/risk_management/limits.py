"""Risk limits — the "risk first" guardrail as a checkable contract.

Hermes-independent, stdlib-only (``math`` + ``dataclasses``). A :class:`Limit`
is a named threshold on a *metric* (a number the caller computes with the
portfolio/quant/derivatives engines — gross exposure, position weight, HHI,
VaR, CVaR, vol, drawdown, …). The checker compares the current value against
the threshold and reports whether it is breached, how close it is, and how
much headroom remains.

Conventions:

- ``direction="max"`` (default) — breach when ``current > threshold``. The
  natural shape for exposure, concentration, VaR, volatility, drawdown.
- ``direction="min"`` — breach when ``current < threshold``. For "at least"
  constraints (minimum diversification, minimum Sharpe, minimum coverage).
- **A limit that references a metric the caller did not supply raises**, not
  silently passes. Fabricating a "pass" on a missing metric is exactly the
  failure this layer exists to prevent.
- ``utilization`` is the ratio of how close the current value is to the limit
  (``current / threshold`` for max, ``threshold / current`` for min); ``1.0``
  means "at the limit", ``> 1.0`` means "through it". ``headroom`` is the
  signed distance to breach (positive while safe, negative once breached).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Limit:
    """A single risk limit: a named threshold on one metric."""

    name: str
    metric: str
    threshold: float
    direction: str = "max"

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("a limit needs a non-empty name")
        if not str(self.metric).strip():
            raise ValueError(f"limit {self.name!r} needs a non-empty metric")
        if self.direction not in ("max", "min"):
            raise ValueError("direction must be 'max' or 'min'")
        if not math.isfinite(float(self.threshold)):
            raise ValueError(f"limit {self.name!r} threshold must be finite")
        if self.direction == "max" and float(self.threshold) <= 0:
            raise ValueError(f"max-limit {self.name!r} needs a positive threshold")
        if self.direction == "min" and float(self.threshold) == 0:
            raise ValueError(f"min-limit {self.name!r} needs a non-zero threshold")


@dataclass
class LimitResult:
    """The outcome of checking one limit against its current value."""

    name: str
    metric: str
    current: float
    threshold: float
    direction: str
    breached: bool
    utilization: float
    headroom: float


@dataclass
class LimitsReport:
    """A full limits check: per-limit results plus a breach summary."""

    results: List[LimitResult]
    breached: List[str]
    worst: LimitResult
    breach_count: int


def check_limit(limit: Limit, current: float) -> LimitResult:
    """Evaluate one limit against a current metric value."""
    current = float(current)
    if not math.isfinite(current):
        raise ValueError(f"current value for limit {limit.name!r} must be finite")
    if limit.direction == "max":
        utilization = current / float(limit.threshold)
        breached = current > float(limit.threshold)
        headroom = float(limit.threshold) - current
    else:  # "min"
        if current == 0:
            raise ValueError(
                f"current value for min-limit {limit.name!r} is zero; utilization undefined"
            )
        utilization = float(limit.threshold) / current
        breached = current < float(limit.threshold)
        headroom = current - float(limit.threshold)
    return LimitResult(
        name=limit.name,
        metric=limit.metric,
        current=current,
        threshold=float(limit.threshold),
        direction=limit.direction,
        breached=breached,
        utilization=utilization,
        headroom=headroom,
    )


def check_limits(limits: list, metrics: Dict[str, float]) -> LimitsReport:
    """Check every limit against the supplied metrics.

    ``metrics`` maps a metric name to its current value. A limit whose metric
    is absent raises rather than fabricating a pass.
    """
    limits = list(limits)
    if not limits:
        raise ValueError("no limits to check")
    results: List[LimitResult] = []
    for limit in limits:
        if limit.metric not in metrics:
            raise ValueError(
                f"limit {limit.name!r} references unknown metric {limit.metric!r}"
            )
        results.append(check_limit(limit, metrics[limit.metric]))
    breached = [r.name for r in results if r.breached]
    worst = max(results, key=lambda r: r.utilization)
    return LimitsReport(
        results=results,
        breached=breached,
        worst=worst,
        breach_count=len(breached),
    )
