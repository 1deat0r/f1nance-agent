"""F1NANCE deal-memo engine — the Phase-11 integration layer.

Hermes-independent, stdlib-only (``math`` + ``dataclasses``). Composes the
M&A engine (accretion/dilution, synergy value + break-even, LBO) with the
risk-management engine (limits + scenario stress) into a single scored
``DealMemo`` — one verdict over the whole deal, derived from the numbers
rather than asserted. It never fabricates: a section that cannot be computed
is recorded as ``not_computed`` with its reason, and the recommendation is a
pure function of the scorecard (``favorable`` / ``adverse`` /
``inconclusive``).
"""

from .memo import (
    RECOMMENDATIONS,
    VERDICTS,
    Check,
    DealMemo,
    build_deal_memo,
)

__version__ = "0.1.0"

__all__ = [
    "RECOMMENDATIONS",
    "VERDICTS",
    "Check",
    "DealMemo",
    "build_deal_memo",
    "__version__",
]
