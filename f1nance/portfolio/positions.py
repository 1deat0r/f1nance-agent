"""Position-level portfolio arithmetic: weights, exposure, FX, cash drag.

Hermes-independent by design: standard library only (``dataclasses`` +
``math``). This is the Phase-2 counterpart to the ``f1nance.data`` substrate:
where the data layer guarantees a number is never fabricated, this module
guarantees a portfolio number is never *arithmetically* fabricated — every
market value, weight, and exposure is computed from explicit inputs, and a
missing FX rate raises instead of guessing.

Conventions (read these before trusting a number out):

- **Base currency.** All cross-currency values are converted to
  ``base_currency`` (default USD) via ``fx_rates``, a mapping
  ``currency -> units of base currency per 1 unit of currency``.
  ``base_currency`` itself is always 1.0 and never looked up.
- **Weights are fractions of total NAV, cash included.** A weight is
  ``base_value / total_nav`` where ``total_nav`` includes cash, so ``weights()``
  sums to 1.0 when cash is present and cash is the residual. Pass
  ``include_cash=False`` to drop cash from the holdings list (the remaining
  weights still divide by total NAV).
- **Exposure is sign-aware and quoted as a multiple of NAV.** A long-only
  fully-invested portfolio has gross == net == 1.0. Shorts push gross above
  net; leverage pushes gross above 1.0.
- **Cash drag** is the return you give up by holding cash instead of the risky
  asset: ``cash_weight * (asset_return - cash_return)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


class MissingFxRate(ValueError):
    """A position or cash balance is denominated in a currency with no FX rate.

    Raised instead of inventing a conversion rate. Provide
    ``Portfolio.fx_rates[<ccy>]`` to resolve.
    """


class InvalidPortfolio(ValueError):
    """The portfolio cannot be valued or rebalanced (e.g. zero NAV, bad weights)."""


@dataclass
class Position:
    """A single holding: ``quantity`` units of ``asset`` at ``price``.

    ``quantity`` may be negative (a short). ``cost_basis`` is the per-unit
    acquisition cost in ``currency`` (optional); without it, P&L is unknown
    rather than zero.
    """

    asset: str
    quantity: float
    price: float
    currency: str = "USD"
    asset_class: str = "equity"
    cost_basis: Optional[float] = None

    def local_value(self) -> float:
        """Market value in the position's own currency (quantity × price)."""
        return self.quantity * self.price

    def is_short(self) -> bool:
        return self.quantity < 0

    def unrealized_pnl(self) -> Optional[float]:
        """Unrealized P&L in ``currency``, or None if cost basis is unknown."""
        if self.cost_basis is None:
            return None
        return self.quantity * (self.price - self.cost_basis)


@dataclass
class Holding:
    """A resolved holding: local and base-currency value plus its NAV weight."""

    asset: str
    asset_class: str
    currency: str
    local_value: float
    base_value: float
    weight: float


@dataclass
class Exposure:
    """Gross/net exposure as multiples of NAV (cash excluded)."""

    long: float
    short: float
    gross: float
    net: float


@dataclass
class Portfolio:
    """A set of positions plus cash, valued in a single base currency."""

    positions: List[Position] = field(default_factory=list)
    cash: Dict[str, float] = field(default_factory=dict)  # currency -> amount
    base_currency: str = "USD"
    fx_rates: Dict[str, float] = field(default_factory=dict)  # ccy -> base per 1 ccy

    # --- FX -----------------------------------------------------------------

    def fx(self, currency: str) -> float:
        """Units of base currency per 1 unit of ``currency``."""
        if currency == self.base_currency:
            return 1.0
        rate = self.fx_rates.get(currency)
        if rate is None:
            raise MissingFxRate(
                f"no FX rate for {currency} -> {self.base_currency}; "
                f"set Portfolio.fx_rates['{currency}']"
            )
        return rate

    # --- valuation ----------------------------------------------------------

    def cash_base_value(self) -> float:
        """Total cash, converted to base currency."""
        return sum(amount * self.fx(ccy) for ccy, amount in self.cash.items())

    def position_base_values(self) -> Dict[str, float]:
        """Per-asset market value in base currency (signed: shorts are negative)."""
        return {
            p.asset: p.quantity * p.price * self.fx(p.currency)
            for p in self.positions
        }

    def market_value(self, include_cash: bool = True) -> float:
        """Net asset value in base currency (positions + cash by default)."""
        total = sum(self.position_base_values().values())
        if include_cash:
            total += self.cash_base_value()
        return total

    def holdings(self, include_cash: bool = True) -> List[Holding]:
        """Resolved holdings with weights. Weights divide by total NAV (cash in)."""
        nav = self.market_value(include_cash=True)
        if nav == 0:
            raise InvalidPortfolio("portfolio has zero NAV; weights are undefined")
        out: List[Holding] = []
        for p in self.positions:
            base = p.quantity * p.price * self.fx(p.currency)
            out.append(Holding(
                asset=p.asset,
                asset_class=p.asset_class,
                currency=p.currency,
                local_value=p.local_value(),
                base_value=base,
                weight=base / nav,
            ))
        if include_cash:
            for ccy, amount in sorted(self.cash.items()):
                if amount == 0:
                    continue
                base = amount * self.fx(ccy)
                out.append(Holding(
                    asset="CASH", asset_class="cash", currency=ccy,
                    local_value=amount, base_value=base, weight=base / nav,
                ))
        return out

    def weights(self, include_cash: bool = True) -> Dict[str, float]:
        """Asset -> weight (fraction of total NAV, cash included by default)."""
        return {h.asset: h.weight for h in self.holdings(include_cash=include_cash)}

    def cash_weight(self) -> float:
        nav = self.market_value(include_cash=True)
        if nav == 0:
            return 0.0
        return self.cash_base_value() / nav

    # --- exposure -----------------------------------------------------------

    def exposure(self) -> Exposure:
        """Long/short/gross/net exposure as multiples of NAV (cash excluded)."""
        nav = self.market_value(include_cash=True)
        if nav == 0:
            raise InvalidPortfolio("portfolio has zero NAV; exposure is undefined")
        long = short = 0.0
        for p in self.positions:
            base = p.quantity * p.price * self.fx(p.currency)
            if base >= 0:
                long += base
            else:
                short += -base
        return Exposure(
            long=long / nav,
            short=short / nav,
            gross=(long + short) / nav,
            net=(long - short) / nav,
        )

    def exposure_by_class(self) -> Dict[str, float]:
        """Signed (net) exposure per asset class as a fraction of NAV."""
        nav = self.market_value(include_cash=True)
        if nav == 0:
            raise InvalidPortfolio("portfolio has zero NAV; exposure is undefined")
        by_class: Dict[str, float] = {}
        for p in self.positions:
            base = p.quantity * p.price * self.fx(p.currency)
            by_class[p.asset_class] = by_class.get(p.asset_class, 0.0) + base
        return {k: v / nav for k, v in sorted(by_class.items())}

    # --- cash drag ----------------------------------------------------------

    def cash_drag(self, asset_return: float, cash_return: float = 0.0) -> float:
        """Return (in return units) forgone by holding cash instead of the asset.

        ``asset_return`` is the period return the invested portion earned;
        ``cash_return`` is what cash earned (default 0.0 for idle cash). The
        drag is ``cash_weight * (asset_return - cash_return)``.
        """
        return self.cash_weight() * (asset_return - cash_return)


def rebalance_trades(
    current_values: Dict[str, float],
    target_weights: Dict[str, float],
    total_value: Optional[float] = None,
) -> Dict[str, float]:
    """Dollar deltas to move a set of holdings to ``target_weights``.

    ``current_values`` maps asset -> current base-currency value;
    ``target_weights`` maps asset -> desired NAV fraction (must sum to 1.0).
    Returns asset -> signed dollar delta (positive = buy, negative = sell).
    Assets present only in ``current_values`` get a full-sell delta.
    """
    total = total_value if total_value is not None else sum(current_values.values())
    if total == 0:
        raise InvalidPortfolio("total value is zero; cannot rebalance")
    target_sum = sum(target_weights.values())
    if abs(target_sum - 1.0) > 1e-9:
        raise InvalidPortfolio(f"target weights sum to {target_sum}, not 1.0")
    deltas: Dict[str, float] = {}
    for asset, weight in target_weights.items():
        deltas[asset] = weight * total - current_values.get(asset, 0.0)
    for asset in current_values:
        if asset not in target_weights:
            deltas[asset] = -current_values[asset]
    return deltas
