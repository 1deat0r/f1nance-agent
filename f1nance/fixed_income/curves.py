"""Yield-curve math — discount factors, spot/forward rates, PV, bootstrapping.

Hermes-independent, stdlib-only. Rates are **annualized decimal** (``0.05`` =
5% per year); times are **years**; ``compounding`` is a positive integer
(periods per year: ``1`` annual, ``2`` semiannual, ``12`` monthly) or the
string ``"continuous"``.

Conventions:

- ``discount_factor(rate, t)`` discounts one unit from ``t`` back to now.
- ``spot_rate(df, t)`` inverts a discount factor back into an annualized spot.
- ``forward_rate`` is the annualized rate from ``t1`` to ``t2`` implied by two
  spot rates; it may be **negative** (an inverted curve is a real market
  state, not an error).
- ``interpolate_spot`` is **linear on annualized spot rates** (not on discount
  factors) and **raises outside the curve range** — no silent extrapolation.
- ``bootstrap_spot_curve`` assumes annual-coupon par bonds at consecutive
  integer-year tenors (``1, 2, …, N``). It is the textbook bootstrap and the
  only form unambiguous without a day-count / coupon-date convention.

Degenerate input raises: negative time, a rate that implies a non-positive
discount factor, non-increasing tenors, a bootstrap that produces a
non-positive discount factor.
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple, Union


def _compounding(compounding) -> Tuple[bool, int]:
    """Return ``(is_continuous, periods_per_year)`` from a compounding spec."""
    if compounding == "continuous":
        return True, 0
    m = int(compounding)
    if m < 1:
        raise ValueError(
            "compounding must be a positive integer (periods per year) or 'continuous'"
        )
    return False, m


def discount_factor(rate: float, t: float, compounding: Union[int, str] = 2) -> float:
    """Discount factor for an annualized ``rate`` over ``t`` years.

    ``(1 + rate/m)^(-m·t)`` for discrete compounding, ``exp(-rate·t)`` for
    continuous. Raises on negative time or a rate that makes the discount
    factor non-positive (meaningless).
    """
    rate = float(rate)
    t = float(t)
    if t < 0:
        raise ValueError("time must be non-negative")
    cont, m = _compounding(compounding)
    if cont:
        return math.exp(-rate * t)
    if 1.0 + rate / m <= 0:
        raise ValueError(f"rate {rate} implies a non-positive discount factor")
    return (1.0 + rate / m) ** (-m * t)


def spot_rate(df: float, t: float, compounding: Union[int, str] = 2) -> float:
    """Annualized spot rate implied by a discount factor at time ``t``."""
    df = float(df)
    t = float(t)
    if t <= 0:
        raise ValueError("time must be positive")
    if df <= 0:
        raise ValueError("discount factor must be positive")
    cont, m = _compounding(compounding)
    if cont:
        return -math.log(df) / t
    return m * (df ** (-1.0 / (m * t)) - 1.0)


def forward_rate(rate_t1: float, rate_t2: float, t1: float, t2: float, compounding: Union[int, str] = 2) -> float:
    """Annualized forward rate from ``t1`` to ``t2`` implied by two spot rates.

    Requires ``0 <= t1 < t2``. A negative result is legitimate (inverted
    curve); only the ordering of the two times is degenerate.
    """
    rate_t1 = float(rate_t1)
    rate_t2 = float(rate_t2)
    t1 = float(t1)
    t2 = float(t2)
    if t1 < 0 or t2 <= t1:
        raise ValueError("require 0 <= t1 < t2")
    df1 = discount_factor(rate_t1, t1, compounding)
    df2 = discount_factor(rate_t2, t2, compounding)
    tau = t2 - t1
    cont, m = _compounding(compounding)
    if cont:
        return math.log(df1 / df2) / tau
    return m * ((df1 / df2) ** (1.0 / (m * tau)) - 1.0)


def pv(cashflows: Sequence[float], times: Sequence[float], rate: float, compounding: Union[int, str] = 2) -> float:
    """Present value of cash flows at a single flat annualized ``rate``.

    ``cashflows`` and ``times`` are parallel lists; ``times`` are in years.
    """
    cfs = [float(c) for c in cashflows]
    ts = [float(t) for t in times]
    if len(cfs) != len(ts):
        raise ValueError("cashflows and times must be the same length")
    return sum(c * discount_factor(rate, t, compounding) for c, t in zip(cfs, ts))


def interpolate_spot(tenors: Sequence[float], spots: Sequence[float], t: float) -> float:
    """Linearly interpolate an annualized spot rate at tenor ``t`` (years).

    Linear on spot rates. Raises when ``t`` lies outside ``[tenors[0],
    tenors[-1]]`` — extrapolation would fabricate a rate the curve does not
    contain.
    """
    tenors = [float(x) for x in tenors]
    spots = [float(s) for s in spots]
    if len(tenors) != len(spots):
        raise ValueError("tenors and spots must be the same length")
    if len(tenors) < 2:
        raise ValueError("interpolation needs at least two curve points")
    for i in range(len(tenors) - 1):
        if tenors[i] >= tenors[i + 1]:
            raise ValueError("tenors must be strictly increasing")
    t = float(t)
    if t < tenors[0] or t > tenors[-1]:
        raise ValueError(f"t={t} is outside the curve range [{tenors[0]}, {tenors[-1]}]")
    if t == tenors[-1]:
        return spots[-1]
    for i in range(len(tenors) - 1):
        if t <= tenors[i + 1]:
            t0, t1 = tenors[i], tenors[i + 1]
            s0, s1 = spots[i], spots[i + 1]
            frac = (t - t0) / (t1 - t0)
            return s0 + frac * (s1 - s0)
    raise AssertionError("unreachable")  # pragma: no cover


def pv_curve(
    cashflows: Sequence[float],
    times: Sequence[float],
    tenors: Sequence[float],
    spots: Sequence[float],
    compounding: Union[int, str] = 2,
) -> float:
    """Present value of cash flows discounted along an interpolated spot curve."""
    cfs = [float(c) for c in cashflows]
    ts = [float(t) for t in times]
    if len(cfs) != len(ts):
        raise ValueError("cashflows and times must be the same length")
    total = 0.0
    for c, t in zip(cfs, ts):
        s = interpolate_spot(tenors, spots, t)
        total += c * discount_factor(s, t, compounding)
    return total


def bootstrap_spot_curve(par_tenors: Sequence[float], par_yields: Sequence[float]) -> Tuple[list, list]:
    """Bootstrap a spot curve from par yields (annual-coupon par bonds).

    ``par_tenors`` must be ``1, 2, …, N`` (consecutive integer years); each
    ``par_yields[i]`` is the annualized yield of a bond priced at par with
    annual coupons. Returns ``(tenors, spots)`` with annualized spot rates
    under annual compounding. Raises if the tenors are not consecutive
    integers or if a bootstrapped discount factor turns non-positive.
    """
    tenors = [float(t) for t in par_tenors]
    yields = [float(y) for y in par_yields]
    if len(tenors) != len(yields):
        raise ValueError("par_tenors and par_yields must be the same length")
    if not tenors:
        raise ValueError("need at least one par point")
    for i, t in enumerate(tenors):
        if abs(t - (i + 1)) > 1e-9:
            raise ValueError("bootstrap requires tenors 1, 2, ..., N (annual-coupon par bonds)")

    spots: list = []
    dfs: dict = {}  # tenor -> discount factor (annual compounding)
    for n, y in zip(range(1, len(tenors) + 1), yields):
        c = y  # a par bond's coupon equals its yield
        if 1.0 + c <= 0:
            raise ValueError(f"par yield {y} implies a non-positive coupon factor")
        coupon_pv = sum(dfs[k] for k in range(1, n))  # empty for n == 1
        df_n = (1.0 - c * coupon_pv) / (1.0 + c)
        if df_n <= 0:
            raise ValueError(f"par yield {y} implies a non-positive discount factor at tenor {n}")
        dfs[n] = df_n
        spots.append(df_n ** (-1.0 / n) - 1.0)
    return tenors, spots
