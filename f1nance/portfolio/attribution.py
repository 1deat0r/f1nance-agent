"""Performance attribution — allocation vs. selection (Brinson-Fachler).

Hermes-independent: standard library only. Given a portfolio and a benchmark,
both expressed as per-asset weights and per-asset period returns, this
decomposes the *active return* (portfolio minus benchmark) into:

- **Allocation effect** — return from being overweight/underweight an asset
  relative to the benchmark, times that asset's *benchmark* return in excess
  of the benchmark total.
- **Selection effect** — return from holding assets that beat their benchmark
  counterpart, at the *benchmark* weight.
- **Interaction** — the joint effect of differing weight AND differing return.

Sums check exactly: allocation + selection + interaction == active return.

Brinson-Fachler formulas (per asset ``i``):

    allocation = (w_p − w_b) · (r_b − R_b)
    selection  = w_b · (r_p − r_b)
    interaction = (w_p − w_b) · (r_p − r_b)

where ``R_b = Σ w_b·r_b`` is the benchmark total return.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class AttributionRow:
    asset: str
    portfolio_weight: float
    benchmark_weight: float
    portfolio_return: float
    benchmark_return: float
    allocation_effect: float
    selection_effect: float
    interaction: float


@dataclass
class AttributionResult:
    rows: List[AttributionRow] = field(default_factory=list)
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    active_return: float = 0.0
    allocation_total: float = 0.0
    selection_total: float = 0.0
    interaction_total: float = 0.0


def brinson(
    portfolio_weights: Dict[str, float],
    benchmark_weights: Dict[str, float],
    portfolio_returns: Dict[str, float],
    benchmark_returns: Dict[str, float],
) -> AttributionResult:
    """Brinson-Fachler attribution over the union of assets in the four dicts.

    Missing weights are treated as 0.0 ("not held"); missing returns are
    treated as 0.0 (e.g. cash). Callers should pass aligned dicts; the 0.0
    convention is documented rather than guessed, so a cash line with no
    return is honest, not fabricated.
    """
    assets = sorted(
        set(portfolio_weights)
        | set(benchmark_weights)
        | set(portfolio_returns)
        | set(benchmark_returns)
    )
    benchmark_total = sum(benchmark_weights.get(a, 0.0) * benchmark_returns.get(a, 0.0)
                          for a in assets)
    portfolio_total = sum(portfolio_weights.get(a, 0.0) * portfolio_returns.get(a, 0.0)
                          for a in assets)

    rows: List[AttributionRow] = []
    alloc_total = sel_total = inter_total = 0.0
    for asset in assets:
        w_p = portfolio_weights.get(asset, 0.0)
        w_b = benchmark_weights.get(asset, 0.0)
        r_p = portfolio_returns.get(asset, 0.0)
        r_b = benchmark_returns.get(asset, 0.0)

        allocation = (w_p - w_b) * (r_b - benchmark_total)
        selection = w_b * (r_p - r_b)
        interaction = (w_p - w_b) * (r_p - r_b)

        alloc_total += allocation
        sel_total += selection
        inter_total += interaction

        rows.append(AttributionRow(
            asset=asset,
            portfolio_weight=w_p,
            benchmark_weight=w_b,
            portfolio_return=r_p,
            benchmark_return=r_b,
            allocation_effect=allocation,
            selection_effect=selection,
            interaction=interaction,
        ))

    return AttributionResult(
        rows=rows,
        portfolio_return=portfolio_total,
        benchmark_return=benchmark_total,
        active_return=portfolio_total - benchmark_total,
        allocation_total=alloc_total,
        selection_total=sel_total,
        interaction_total=inter_total,
    )
