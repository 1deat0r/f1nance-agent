"""Transaction-cost model: slippage and market impact.

A trade is costed before it is placed. The cost of a round is the half-spread
you cross, the market impact of your own size (square-root law over
participation), and explicit fees — all in basis points, plus the currency
total. Degenerate input raises; nothing here fabricates a fill or a cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CostEstimate:
    notional: float
    participation: float          # notional / ADV
    spread_bps: float             # half-spread charged per side
    market_impact_bps: float
    fee_bps: float
    total_bps: float
    total_cost: float             # currency
    impact_zone: bool             # participation above 10% of ADV
    warnings: list = field(default_factory=list)


def participation_rate(notional: float, adv: float) -> float:
    """Fraction of the day's volume a trade represents (notional / ADV)."""
    if notional <= 0:
        raise ValueError("notional must be positive")
    if adv <= 0:
        raise ValueError("ADV must be positive")
    return notional / adv


def market_impact_bps(participation: float, sigma_daily_bps: float = 100.0,
                      coefficient: float = 0.1) -> float:
    """Square-root impact model: ``sigma * coefficient * sqrt(participation)``.

    ``sigma_daily_bps`` is the instrument's daily volatility in bps;
    ``coefficient`` is the Almgren-style impact constant (0.1 is a common
    order-of-magnitude default).
    """
    if participation <= 0:
        raise ValueError("participation must be positive")
    if sigma_daily_bps < 0:
        raise ValueError("sigma_daily_bps must be non-negative")
    if coefficient < 0:
        raise ValueError("coefficient must be non-negative")
    return sigma_daily_bps * coefficient * (participation ** 0.5)


def estimate_cost(notional: float, adv: float, *, spread_bps: float = 5.0,
                  fee_bps: float = 1.0, sigma_daily_bps: float = 100.0,
                  coefficient: float = 0.1) -> CostEstimate:
    """Estimate the total transaction cost of a trade in bps and currency."""
    if spread_bps < 0:
        raise ValueError("spread_bps must be non-negative")
    if fee_bps < 0:
        raise ValueError("fee_bps must be non-negative")
    participation = participation_rate(notional, adv)
    if participation > 1.0:
        raise ValueError(
            f"notional {notional:.2f} exceeds the day's volume (participation "
            f"{participation:.1%} > 100%)"
        )
    half_spread = spread_bps / 2.0
    impact = market_impact_bps(participation, sigma_daily_bps, coefficient)
    total_bps = half_spread + impact + fee_bps
    total_cost = notional * total_bps / 10_000.0
    warnings = []
    impact_zone = participation > 0.10
    if impact_zone:
        warnings.append(
            f"participation {participation:.1%} exceeds 10% of ADV; "
            f"market impact is material"
        )
    return CostEstimate(
        notional=notional,
        participation=participation,
        spread_bps=half_spread,
        market_impact_bps=impact,
        fee_bps=fee_bps,
        total_bps=total_bps,
        total_cost=total_cost,
        impact_zone=impact_zone,
        warnings=warnings,
    )
