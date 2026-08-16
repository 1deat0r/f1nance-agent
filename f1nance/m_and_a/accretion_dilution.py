"""Merger accretion / dilution — the EPS bridge across a deal.

Hermes-independent, stdlib-only (``math`` + ``dataclasses``). Given the
acquirer's and target's standalone net income, the consideration paid (split
into cash and stock), the synergies expected, and the financing terms, this
computes the combined entity's pro-forma EPS and the accretion (or dilution)
against the acquirer's standalone EPS.

Conventions:

- All money in the same currency. ``acquirer_ni`` / ``target_ni`` are
  **standalone net income**; ``acquirer_shares`` is shares outstanding.
- ``purchase_price`` is the total equity consideration; ``cash_portion`` +
  ``stock_portion`` must sum to it (validated — a deal that does not balance
  raises). Stock consideration is converted to new shares at
  ``acquirer_share_price``.
- The cash portion is funded by a mix of ``cash_used`` (cash on hand, forgoing
  interest at ``cash_yield``) and new debt of ``cash_portion - cash_used``
  (paying ``new_debt_rate``). Financing cost is tax-affected at ``tax_rate``.
- Synergies (``cost_synergies`` + ``revenue_synergies``) are **pre-tax** and
  tax-affected the same way.

  Pro-forma NI = NI_A + NI_T + (synergies − financing cost) × (1 − tax)
  Pro-forma EPS = pro-forma NI / (shares_A + new shares)

- The accretion is reported in both absolute ($ per share) and relative terms.
  The relative term (``accretion_pct``) is only meaningful when the acquirer's
  standalone EPS is positive; it is ``None`` otherwise, and the ``accretive``
  flag is the unambiguous reading.

Degenerate input raises: non-positive acquirer shares, non-positive purchase
price, a cash/stock split that does not equal the price, a non-positive
acquirer share price when stock is used, a tax rate outside ``[0, 1)``, cash
used outside ``[0, cash_portion]``, or non-finite rates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

_TOL = 1e-9


@dataclass
class AccretionResult:
    """The full EPS bridge across a merger."""

    standalone_eps: float
    pro_forma_eps: float
    accretion_abs: float
    accretion_pct: Optional[float]
    accretive: bool
    pro_forma_ni: float
    new_shares: float
    pro_forma_shares: float
    synergies_after_tax: float
    financing_cost_after_tax: float
    new_debt: float


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def accretion_dilution(
    acquirer_ni: float,
    acquirer_shares: float,
    target_ni: float,
    purchase_price: float,
    cash_portion: float,
    stock_portion: float,
    acquirer_share_price: float,
    tax_rate: float,
    cost_synergies: float = 0.0,
    revenue_synergies: float = 0.0,
    new_debt_rate: float = 0.0,
    cash_used: float = 0.0,
    cash_yield: float = 0.0,
) -> AccretionResult:
    """Compute the pro-forma EPS and accretion of a cash/stock merger.

    ``cash_portion + stock_portion`` must equal ``purchase_price``. The cash
    portion is funded by ``cash_used`` (forgoing ``cash_yield``) and new debt
    of ``cash_portion - cash_used`` (paying ``new_debt_rate``). Synergies and
    financing costs are tax-affected at ``tax_rate``.
    """
    acquirer_ni = _finite("acquirer_ni", acquirer_ni)
    target_ni = _finite("target_ni", target_ni)
    acquirer_shares = _finite("acquirer_shares", acquirer_shares)
    purchase_price = _finite("purchase_price", purchase_price)
    cash_portion = _finite("cash_portion", cash_portion)
    stock_portion = _finite("stock_portion", stock_portion)
    acquirer_share_price = _finite("acquirer_share_price", acquirer_share_price)
    tax_rate = _finite("tax_rate", tax_rate)
    cost_synergies = _finite("cost_synergies", cost_synergies)
    revenue_synergies = _finite("revenue_synergies", revenue_synergies)
    new_debt_rate = _finite("new_debt_rate", new_debt_rate)
    cash_used = _finite("cash_used", cash_used)
    cash_yield = _finite("cash_yield", cash_yield)

    if acquirer_shares <= 0:
        raise ValueError("acquirer_shares must be positive")
    if purchase_price <= 0:
        raise ValueError("purchase_price must be positive")
    if cash_portion < 0:
        raise ValueError("cash_portion must be non-negative")
    if stock_portion < 0:
        raise ValueError("stock_portion must be non-negative")
    scale = max(1.0, abs(purchase_price))
    if abs((cash_portion + stock_portion) - purchase_price) > _TOL * scale:
        raise ValueError(
            "cash_portion + stock_portion must equal purchase_price "
            f"(got {cash_portion} + {stock_portion} != {purchase_price})"
        )
    if stock_portion > 0 and acquirer_share_price <= 0:
        raise ValueError("acquirer_share_price must be positive when stock is used")
    if not (0.0 <= tax_rate < 1.0):
        raise ValueError("tax_rate must be in [0, 1)")
    if cash_used < 0 or cash_used > cash_portion:
        raise ValueError("cash_used must be within [0, cash_portion]")

    new_debt = cash_portion - cash_used
    synergies_pre_tax = cost_synergies + revenue_synergies
    synergies_after_tax = synergies_pre_tax * (1.0 - tax_rate)
    interest_on_new_debt = new_debt * new_debt_rate
    forgone_interest = cash_used * cash_yield
    financing_cost_pre_tax = interest_on_new_debt + forgone_interest
    financing_cost_after_tax = financing_cost_pre_tax * (1.0 - tax_rate)

    pro_forma_ni = (
        acquirer_ni
        + target_ni
        + synergies_after_tax
        - financing_cost_after_tax
    )
    new_shares = stock_portion / acquirer_share_price if stock_portion > 0 else 0.0
    pro_forma_shares = acquirer_shares + new_shares

    standalone_eps = acquirer_ni / acquirer_shares
    pro_forma_eps = pro_forma_ni / pro_forma_shares
    accretion_abs = pro_forma_eps - standalone_eps
    accretion_pct = (
        accretion_abs / standalone_eps if standalone_eps != 0 else None
    )
    return AccretionResult(
        standalone_eps=standalone_eps,
        pro_forma_eps=pro_forma_eps,
        accretion_abs=accretion_abs,
        accretion_pct=accretion_pct,
        accretive=accretion_abs > 0,
        pro_forma_ni=pro_forma_ni,
        new_shares=new_shares,
        pro_forma_shares=pro_forma_shares,
        synergies_after_tax=synergies_after_tax,
        financing_cost_after_tax=financing_cost_after_tax,
        new_debt=new_debt,
    )
