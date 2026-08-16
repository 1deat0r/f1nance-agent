"""F1NANCE M&A engine — Phase-10 native core.

Hermes-independent, stdlib-only (``math`` + ``dataclasses``). The deal-mechanics
layer that sits on top of the valuation skill (DCF, comps, precedent
transactions): once a target is valued, this package prices the *deal* — the
EPS bridge (accretion/dilution), the synergy bet that justifies the premium,
and the leveraged-buyout return. It never fabricates a number: a deal that
does not balance, a synergy model that needs ``r <= g``, or an over-levered
capitalization all raise rather than producing a plausible-looking answer.

Three modules:

- ``accretion_dilution`` — pro-forma EPS and accretion/dilution of a
  cash/stock merger (synergies and financing costs tax-affected).
- ``synergies`` — present-value the run-rate synergies (ramp + perpetuity) and
  net them against integration costs and the premium; plus the break-even run-rate.
- ``lbo`` — a leveraged buyout: sources & uses, a year-by-year debt schedule
  (FCF → debt paydown), the exit, and the sponsor's MOIC/IRR.
"""

from .accretion_dilution import AccretionResult, accretion_dilution
from .lbo import LboResult, LboYear, lbo
from .synergies import (
    SynergyBreakeven,
    SynergyValue,
    synergy_breakeven,
    synergy_value,
)

__version__ = "0.1.0"

__all__ = [
    "AccretionResult",
    "LboResult",
    "LboYear",
    "SynergyBreakeven",
    "SynergyValue",
    "accretion_dilution",
    "lbo",
    "synergy_breakeven",
    "synergy_value",
    "__version__",
]
