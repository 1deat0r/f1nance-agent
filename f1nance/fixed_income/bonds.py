"""Bond pricing and risk measures — stdlib-only, no day-count theater.

Hermes-independent, stdlib-only. Prices **clean** bonds (whole coupon
periods) and measures their interest-rate risk.

Conventions:

- ``coupon_rate`` and ``ytm`` are **annualized decimal** (``0.05`` = 5%).
- ``maturity_years`` × ``payments_per_year`` must be a **whole number** of
  periods (a bond between coupon dates needs a day-count convention, which
  this module deliberately does not model — see below).
- ``face`` defaults to 100 (par).
- ``payments_per_year`` defaults to 2 (US semiannual convention).

Degenerate input raises: non-positive maturity, non-integer period count, a
yield that makes a discount factor non-positive, a non-positive price.

Deliberately not modeled (kept out rather than done half-right):

- **Day-count / accrued-interest conventions** (Actual/Actual, 30/360, …).
  The engine prices clean; settlement and dirty price are the caller's.
- **Embedded options** (callable/putable bonds) — these need a tree/lattice,
  not closed-form discounting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class BondRisk:
    """Interest-rate risk of a bond at a given yield.

    ``macaulay_duration`` is in years. ``modified_duration`` is the
    percentage price change per unit yield move (in years). ``convexity`` is
    in years². ``dv01`` is the absolute price change per 1 bp (0.01%) yield
    move; ``dollar_duration`` is ``price × modified_duration``.
    """

    macaulay_duration: float
    modified_duration: float
    convexity: float
    dv01: float
    dollar_duration: float


def cashflows(
    coupon_rate: float,
    maturity_years: float,
    face: float = 100.0,
    payments_per_year: int = 2,
) -> List[Tuple[float, float]]:
    """The bond's cash-flow schedule as ``(time_years, amount)`` pairs.

    Coupons are ``face × coupon_rate / payments_per_year``; the final coupon
    date also returns the face. Raises unless ``maturity_years ×
    payments_per_year`` is a whole number.
    """
    coupon_rate = float(coupon_rate)
    maturity_years = float(maturity_years)
    face = float(face)
    ppy = int(payments_per_year)
    if maturity_years <= 0:
        raise ValueError("maturity must be positive")
    if ppy < 1:
        raise ValueError("payments_per_year must be at least 1")
    n = int(round(maturity_years * ppy))
    if n < 1:
        raise ValueError("maturity must cover at least one full period")
    if abs(maturity_years * ppy - n) > 1e-9:
        raise ValueError("maturity_years × payments_per_year must be a whole number")
    coupon = face * coupon_rate / ppy
    out: List[Tuple[float, float]] = []
    for k in range(1, n + 1):
        amount = coupon + (face if k == n else 0.0)
        out.append((k / ppy, amount))
    return out


def bond_price(
    coupon_rate: float,
    maturity_years: float,
    ytm: float,
    face: float = 100.0,
    payments_per_year: int = 2,
) -> float:
    """Clean price of a bond: PV of coupons plus face at the given yield."""
    ytm = float(ytm)
    cfs = cashflows(coupon_rate, maturity_years, face, payments_per_year)
    ppy = int(payments_per_year)
    r = ytm / ppy
    if 1.0 + r <= 0:
        raise ValueError(f"ytm {ytm} implies a non-positive discount factor")
    price = 0.0
    for t, c in cfs:
        k = int(round(t * ppy))
        price += c / (1.0 + r) ** k
    return price


def ytm(
    price: float,
    coupon_rate: float,
    maturity_years: float,
    face: float = 100.0,
    payments_per_year: int = 2,
) -> float:
    """Solve for the annualized yield-to-maturity implied by a clean price.

    Bisection over the yield, exact to floating precision. Negative yields
    are legitimate and returned as-is. Raises on a non-positive price or a
    price the bracket cannot contain.
    """
    price = float(price)
    if price <= 0:
        raise ValueError("price must be positive")
    cfs = cashflows(coupon_rate, maturity_years, face, payments_per_year)
    ppy = int(payments_per_year)

    def px(y: float) -> float:
        r = y / ppy
        if 1.0 + r <= 0:
            return float("inf")
        total = 0.0
        for t, c in cfs:
            k = int(round(t * ppy))
            total += c / (1.0 + r) ** k
        return total

    lo = -0.999999 * ppy  # per-period yield just above -100%
    hi = 10.0 * ppy  # 1000% annualized; px(hi) is near zero
    if not (px(lo) >= price >= px(hi)):
        raise ValueError(f"cannot bracket ytm for price {price}")
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if px(mid) >= price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def duration_and_convexity(
    coupon_rate: float,
    maturity_years: float,
    ytm: float,
    face: float = 100.0,
    payments_per_year: int = 2,
) -> BondRisk:
    """Macaulay/modified duration, convexity, and DV01 at the given yield.

    Closed-form (discrete periods); no finite-difference approximation.
    """
    ytm = float(ytm)
    cfs = cashflows(coupon_rate, maturity_years, face, payments_per_year)
    ppy = int(payments_per_year)
    r = ytm / ppy
    if 1.0 + r <= 0:
        raise ValueError(f"ytm {ytm} implies a non-positive discount factor")
    price = bond_price(coupon_rate, maturity_years, ytm, face, ppy)

    mac = 0.0
    conv_sum = 0.0
    for t, c in cfs:
        k = int(round(t * ppy))
        pv_cf = c / (1.0 + r) ** k
        mac += t * pv_cf
        conv_sum += k * (k + 1) * c / (1.0 + r) ** (k + 2)
    mac /= price
    modified = mac / (1.0 + r)
    convexity = conv_sum / (price * ppy * ppy)
    dv01 = price * modified * 0.0001
    return BondRisk(
        macaulay_duration=mac,
        modified_duration=modified,
        convexity=convexity,
        dv01=dv01,
        dollar_duration=price * modified,
    )
