"""F1NANCE execution & compliance layer — Phase-4 native core.

Hermes-independent, stdlib-only. Built on top of the ``f1nance.data``,
``f1nance.portfolio``, and ``f1nance.quant`` layers: those layers guarantee a
number is never fetched-, arithmetically-, or statistically-fabricated; this
package guarantees an *order is never silently executed* — every decision is
validated, costed, and mirrored in an append-only compliance ledger with its
rationale and confidence.

Three modules:

- ``orders`` — order model (market/limit/stop/stop-limit) and validation,
  including marketability and stop-placement checks against a market price.
- ``impact`` — slippage and market-impact model (half-spread + square-root
  impact + fees) so a trade is costed before it is placed.
- ``ledger`` — the append-only compliance trade log: every decision recorded
  once with rationale/confidence/loss-case, status derived from an immutable
  event stream, and a compliance gate that rejects rather than drops.
"""

from .impact import (
    CostEstimate,
    estimate_cost,
    market_impact_bps,
    participation_rate,
)
from .ledger import (
    DEFAULT_RULES,
    ComplianceEngine,
    Decision,
    Event,
    Ledger,
    confidence_label,
    load_ledger,
    parse_confidence,
    rule_max_notional,
    save_ledger,
)
from .orders import (
    Order,
    OrderAssessment,
    OrderType,
    Side,
    TimeInForce,
    assess,
    validate_order,
)

__version__ = "0.1.0"

__all__ = [
    "CostEstimate",
    "ComplianceEngine",
    "DEFAULT_RULES",
    "Decision",
    "Event",
    "Ledger",
    "Order",
    "OrderAssessment",
    "OrderType",
    "Side",
    "TimeInForce",
    "assess",
    "confidence_label",
    "estimate_cost",
    "load_ledger",
    "market_impact_bps",
    "parse_confidence",
    "participation_rate",
    "rule_max_notional",
    "save_ledger",
    "validate_order",
    "__version__",
]
