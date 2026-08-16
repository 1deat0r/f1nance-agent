"""Synergy valuation — does the deal's premium actually pay for itself?

Hermes-independent, stdlib-only (``math`` + ``dataclasses``). A merger's
premium is a bet on synergies: the buyer pays more than the standalone value
hoping the combination is worth more than the sum of its parts. This module
values that bet — the after-tax run-rate synergies, ramped in over a few years
and grown in perpetuity — and nets it against the one-time integration costs
and the premium paid. The break-even flips the question: given the premium and
integration costs, how much run-rate synergy is *required* just to break even?

Conventions:

- ``cost_synergies`` is the annual **pre-tax** run-rate profit improvement
  (e.g. duplicate SG&A removed). ``revenue_synergies`` is the annual
  **pre-tax** incremental revenue, and ``revenue_margin`` is the operating
  margin on that incremental revenue, so
  ``pre_tax_run_rate = cost_synergies + revenue_synergies * revenue_margin``.
- The after-tax run-rate is ``pre_tax_run_rate * (1 - tax_rate)``.
- Synergies ramp linearly to full run-rate over ``ramp_years`` (year ``t``
  contributes ``t/ramp_years`` of run-rate), then grow in perpetuity at
  ``growth`` (Gordon growth). All discounted at ``discount_rate``.
- ``premium_paid`` is the consideration above the target's standalone value;
  ``integration_costs`` is the one-time cost of combining. Both are subtracted
  from the gross present value.

Degenerate input raises: a non-positive discount rate, ``growth`` at or above
``discount_rate`` (a growing perpetuity needs ``r > g``), ``ramp_years < 1``,
a tax rate or revenue margin outside ``[0, 1)``, or negative
``integration_costs`` / ``premium_paid``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class SynergyValue:
    """The present value of synergies, net of costs and the premium paid."""

    pre_tax_run_rate: float
    after_tax_run_rate: float
    pv_factor: float
    gross_value: float
    integration_costs: float
    premium_paid: float
    net_value: float
    covered: bool


@dataclass
class SynergyBreakeven:
    """The run-rate synergies required to exactly justify the premium."""

    required_cost_synergies: float
    required_after_tax_run_rate: float
    pv_factor: float
    premium_paid: float
    integration_costs: float


def _synergy_pv_factor(discount_rate: float, ramp_years: int, growth: float) -> float:
    """Present value of $1 of run-rate after-tax synergy, ramp + perpetuity."""
    if not math.isfinite(discount_rate) or discount_rate <= 0:
        raise ValueError("discount_rate must be positive")
    if not math.isfinite(growth) or growth < 0:
        raise ValueError("growth must be non-negative")
    if discount_rate <= growth:
        raise ValueError("discount_rate must exceed growth for a growing perpetuity")
    ramp_years = int(ramp_years)
    if ramp_years < 1:
        raise ValueError("ramp_years must be a positive integer")

    pv = 0.0
    for t in range(1, ramp_years + 1):
        frac = t / ramp_years
        pv += frac / (1.0 + discount_rate) ** t
    terminal = (
        (1.0 + growth)
        / (discount_rate - growth)
        / (1.0 + discount_rate) ** ramp_years
    )
    return pv + terminal


def synergy_value(
    cost_synergies: float,
    revenue_synergies: float,
    revenue_margin: float,
    tax_rate: float,
    discount_rate: float,
    ramp_years: int,
    integration_costs: float,
    premium_paid: float,
    growth: float = 0.0,
) -> SynergyValue:
    """Present-value the synergies and net them against costs and the premium."""
    cost_synergies = float(cost_synergies)
    revenue_synergies = float(revenue_synergies)
    revenue_margin = float(revenue_margin)
    tax_rate = float(tax_rate)
    integration_costs = float(integration_costs)
    premium_paid = float(premium_paid)

    if not math.isfinite(cost_synergies) or cost_synergies < 0:
        raise ValueError("cost_synergies must be a non-negative number")
    if not math.isfinite(revenue_synergies) or revenue_synergies < 0:
        raise ValueError("revenue_synergies must be a non-negative number")
    if not (0.0 <= revenue_margin < 1.0):
        raise ValueError("revenue_margin must be in [0, 1)")
    if not (0.0 <= tax_rate < 1.0):
        raise ValueError("tax_rate must be in [0, 1)")
    if not math.isfinite(integration_costs) or integration_costs < 0:
        raise ValueError("integration_costs must be non-negative")
    if not math.isfinite(premium_paid) or premium_paid < 0:
        raise ValueError("premium_paid must be non-negative")

    pre_tax_run_rate = cost_synergies + revenue_synergies * revenue_margin
    after_tax_run_rate = pre_tax_run_rate * (1.0 - tax_rate)
    pv_factor = _synergy_pv_factor(discount_rate, ramp_years, growth)
    gross_value = after_tax_run_rate * pv_factor
    net_value = gross_value - integration_costs - premium_paid
    return SynergyValue(
        pre_tax_run_rate=pre_tax_run_rate,
        after_tax_run_rate=after_tax_run_rate,
        pv_factor=pv_factor,
        gross_value=gross_value,
        integration_costs=integration_costs,
        premium_paid=premium_paid,
        net_value=net_value,
        covered=net_value > 0,
    )


def synergy_breakeven(
    premium_paid: float,
    integration_costs: float,
    tax_rate: float,
    discount_rate: float,
    ramp_years: int,
    growth: float = 0.0,
) -> SynergyBreakeven:
    """Solve the pre-tax run-rate cost synergies that exactly cover the premium.

    Assumes cost synergies only (no revenue synergies). Returns the run-rate
    that makes ``net_value == 0``: enough after-tax synergy value to exactly
    offset ``integration_costs + premium_paid``.
    """
    premium_paid = float(premium_paid)
    integration_costs = float(integration_costs)
    tax_rate = float(tax_rate)

    if not math.isfinite(premium_paid) or premium_paid < 0:
        raise ValueError("premium_paid must be non-negative")
    if not math.isfinite(integration_costs) or integration_costs < 0:
        raise ValueError("integration_costs must be non-negative")
    if not (0.0 <= tax_rate < 1.0):
        raise ValueError("tax_rate must be in [0, 1)")

    pv_factor = _synergy_pv_factor(discount_rate, ramp_years, growth)
    required_after_tax = (premium_paid + integration_costs) / pv_factor
    required_cost = required_after_tax / (1.0 - tax_rate)
    return SynergyBreakeven(
        required_cost_synergies=required_cost,
        required_after_tax_run_rate=required_after_tax,
        pv_factor=pv_factor,
        premium_paid=premium_paid,
        integration_costs=integration_costs,
    )
