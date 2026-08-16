"""Leveraged buyout — sources & uses, the debt schedule, and the sponsor return.

Hermes-independent, stdlib-only (``math`` + ``dataclasses``). A leveraged
buyout buys a company mostly with debt, uses the company's own cash flow to
repay that debt, and exits a few years later — the sponsor's return is the
equity it gets back at exit versus the equity it put in. This module models
that: entry capitalization (sources & uses), a year-by-year debt schedule, the
exit, and the resulting MOIC and IRR.

Conventions:

- ``enterprise_value`` is the EV paid (equity + net debt). ``existing_net_debt``
  is the target's net debt at entry (part of EV; negative means net cash).
  ``fees`` are transaction fees. Total uses = ``enterprise_value + fees``.
- ``entry_debt`` is total debt on the balance sheet at entry (it refinances the
  existing net debt and funds part of the equity). The sponsor's
  ``equity_check`` is the balancing plug: ``enterprise_value + fees - entry_debt``.
- Each year: EBITDA grows at ``ebitda_growth``; unlevered free cash flow is
  ``EBITDA * fcf_margin``; cash interest is ``debt * interest_rate * (1 - tax)``;
  free cash flow = UFCF − cash interest; FCF repays debt (a shortfall increases
  debt; debt is floored at zero and any excess becomes ``cash_build``).
- At exit (year ``years``): ``exit_ev = exit_ebitda * exit_multiple``,
  ``exit_equity = exit_ev - exit_debt + cash_build``. ``moic = exit_equity /
  equity_check``; ``irr = moic ** (1/years) - 1`` (no interim distributions —
  all FCF pays down debt, the standard base LBO).

Degenerate input raises: non-positive enterprise value, non-positive entry
EBITDA, negative fees or entry debt, a non-positive exit multiple, a negative
equity check (the deal does not balance — debt exceeds the uses), ``years < 1``,
a tax rate outside ``[0, 1)``, or a non-finite growth/rate/margin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List


@dataclass
class LboYear:
    """One year of the debt schedule."""

    year: int
    ebitda: float
    ufcf: float
    cash_interest: float
    fcf: float
    debt_end: float
    cash_build: float


@dataclass
class LboResult:
    """The full LBO: entry capitalization, schedule, exit, and sponsor return."""

    enterprise_value: float
    equity_purchase_price: float
    fees: float
    uses_total: float
    entry_debt: float
    equity_check: float
    entry_multiple: float
    exit_multiple: float
    schedule: List[LboYear]
    exit_ebitda: float
    exit_ev: float
    exit_debt: float
    cash_build: float
    exit_equity: float
    moic: float
    irr: float


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def lbo(
    enterprise_value: float,
    existing_net_debt: float,
    fees: float,
    entry_debt: float,
    ebitda_0: float,
    ebitda_growth: float,
    years: int,
    fcf_margin: float,
    exit_multiple: float,
    interest_rate: float,
    tax_rate: float = 0.0,
) -> LboResult:
    """Model an LBO and return the debt schedule, exit, and sponsor return."""
    enterprise_value = _finite("enterprise_value", enterprise_value)
    existing_net_debt = _finite("existing_net_debt", existing_net_debt)
    fees = _finite("fees", fees)
    entry_debt = _finite("entry_debt", entry_debt)
    ebitda_0 = _finite("ebitda_0", ebitda_0)
    ebitda_growth = _finite("ebitda_growth", ebitda_growth)
    fcf_margin = _finite("fcf_margin", fcf_margin)
    exit_multiple = _finite("exit_multiple", exit_multiple)
    interest_rate = _finite("interest_rate", interest_rate)
    tax_rate = _finite("tax_rate", tax_rate)

    if enterprise_value <= 0:
        raise ValueError("enterprise_value must be positive")
    if fees < 0:
        raise ValueError("fees must be non-negative")
    if entry_debt < 0:
        raise ValueError("entry_debt must be non-negative")
    if ebitda_0 <= 0:
        raise ValueError("ebitda_0 must be positive")
    if ebitda_growth <= -1.0:
        raise ValueError("ebitda_growth must be greater than -100%")
    if exit_multiple <= 0:
        raise ValueError("exit_multiple must be positive")
    if interest_rate <= -1.0:
        raise ValueError("interest_rate must be greater than -100%")
    if not (0.0 <= tax_rate < 1.0):
        raise ValueError("tax_rate must be in [0, 1)")
    years = int(years)
    if years < 1:
        raise ValueError("years must be a positive integer")

    uses_total = enterprise_value + fees
    equity_check = uses_total - entry_debt
    if equity_check <= 0:
        raise ValueError(
            "entry_debt exceeds the uses of the deal — equity check would be "
            f"non-positive ({equity_check}); the deal does not balance"
        )

    equity_purchase_price = enterprise_value - existing_net_debt
    entry_multiple = enterprise_value / ebitda_0

    debt = entry_debt
    cash_build = 0.0
    schedule: List[LboYear] = []
    ebitda = ebitda_0
    for year in range(1, years + 1):
        ebitda = ebitda_0 * (1.0 + ebitda_growth) ** year
        ufcf = ebitda * fcf_margin
        cash_interest = debt * interest_rate * (1.0 - tax_rate)
        fcf = ufcf - cash_interest
        debt_end = debt - fcf
        if debt_end < 0:
            cash_build += -debt_end
            debt_end = 0.0
        schedule.append(
            LboYear(
                year=year,
                ebitda=ebitda,
                ufcf=ufcf,
                cash_interest=cash_interest,
                fcf=fcf,
                debt_end=debt_end,
                cash_build=cash_build,
            )
        )
        debt = debt_end

    exit_ebitda = ebitda_0 * (1.0 + ebitda_growth) ** years
    exit_ev = exit_ebitda * exit_multiple
    exit_equity = exit_ev - debt + cash_build
    moic = exit_equity / equity_check
    irr = moic ** (1.0 / years) - 1.0

    return LboResult(
        enterprise_value=enterprise_value,
        equity_purchase_price=equity_purchase_price,
        fees=fees,
        uses_total=uses_total,
        entry_debt=entry_debt,
        equity_check=equity_check,
        entry_multiple=entry_multiple,
        exit_multiple=exit_multiple,
        schedule=schedule,
        exit_ebitda=exit_ebitda,
        exit_ev=exit_ev,
        exit_debt=debt,
        cash_build=cash_build,
        exit_equity=exit_equity,
        moic=moic,
        irr=irr,
    )
