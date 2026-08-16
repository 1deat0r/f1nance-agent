"""Black-Scholes closed-form pricing, Greeks, and implied volatility.

Hermes-independent, stdlib-only (``math`` + ``dataclasses``). This is the
closed-form half of the derivatives engine: the European option under the
Black-Scholes assumptions (log-normal spot, constant vol, continuous risk-free
rate and dividend yield).

Conventions:

- ``S`` (spot) and ``K`` (strike) are in the same currency; ``price`` too.
- ``T`` is time to expiry in **years**.
- ``r`` is the risk-free rate, **annualized decimal** (``0.05`` = 5%), under
  **continuous compounding** — the same convention as the fixed-income
  engine's ``compounding="continuous"``.
- ``sigma`` is volatility, **annualized decimal** (``0.20`` = 20%).
- ``q`` is the continuous dividend yield, annualized decimal (default 0).
- ``call_put`` is ``"call"`` or ``"put"`` (case-insensitive).

The normal CDF uses ``math.erf`` (``N(x) = 0.5 * (1 + erf(x / sqrt(2)))``);
the PDF is ``phi(x) = exp(-x^2/2) / sqrt(2 pi)``.

Degenerate input raises: non-positive spot, strike, time, or volatility.
Negative ``r`` and ``q`` are legal — a negative rate is a real market state,
not an error (mirrors the fixed-income engine's stance on negative yields).

The implied-volatility solver refuses to return a number with no economic
meaning: a market price outside the no-arbitrage bounds of the model (below
intrinsic, above the deep-in-the-money limit) raises rather than fabricating a
"vol" for a price the model cannot contain.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_SQRT_2PI = math.sqrt(2.0 * math.pi)
_IV_LO = 1e-6  # ~0.0001% vol — the intrinsic-value limit
_IV_HI = 5.0  # 500% vol — the deep-in-the-money limit


def normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution ``N(x)`` via ``math.erf``."""
    return 0.5 * (1.0 + math.erf(float(x) / math.sqrt(2.0)))


def normal_pdf(x: float) -> float:
    """Standard normal probability density ``phi(x)``."""
    x = float(x)
    return math.exp(-0.5 * x * x) / _SQRT_2PI


@dataclass
class OptionPrice:
    """The Black-Scholes value and the two ``d``-statistics behind it."""

    price: float
    d1: float
    d2: float


@dataclass
class Greeks:
    """First- and second-order sensitivities, closed-form (no finite difference).

    ``delta``/``gamma``/``vega``/``rho`` are per unit of the underlying
    variable (spot / spot² / 100%-vol / 100%-rate). ``theta`` is the price
    decay **per year** (negative for a long option, all else equal).
    """

    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


def _cp(call_put: str) -> str:
    cp = str(call_put).strip().lower()
    if cp not in ("call", "put"):
        raise ValueError("call_put must be 'call' or 'put'")
    return cp


def _validate_base(call_put: str, S: float, K: float, T: float) -> None:
    _cp(call_put)
    if S <= 0:
        raise ValueError("spot must be positive")
    if K <= 0:
        raise ValueError("strike must be positive")
    if T <= 0:
        raise ValueError("time to expiry must be positive")


def _validate(S: float, K: float, T: float, sigma: float, call_put: str) -> None:
    _validate_base(call_put, S, K, T)
    if sigma <= 0:
        raise ValueError("volatility must be positive")


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float, q: float):
    sqrt_t = math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrt_t)
    return d1, d1 - sigma * sqrt_t


def black_scholes(
    call_put: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> OptionPrice:
    """European option value under Black-Scholes (continuous compounding)."""
    _validate(S, K, T, sigma, call_put)
    cp = _cp(call_put)
    S = float(S)
    K = float(K)
    T = float(T)
    r = float(r)
    sigma = float(sigma)
    q = float(q)
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    df_r = math.exp(-r * T)
    df_q = math.exp(-q * T)
    if cp == "call":
        price = S * df_q * normal_cdf(d1) - K * df_r * normal_cdf(d2)
    else:
        price = K * df_r * normal_cdf(-d2) - S * df_q * normal_cdf(-d1)
    return OptionPrice(price=price, d1=d1, d2=d2)


def greeks(
    call_put: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> Greeks:
    """Closed-form Greeks (delta, gamma, vega, theta, rho) for a European option."""
    _validate(S, K, T, sigma, call_put)
    cp = _cp(call_put)
    S = float(S)
    K = float(K)
    T = float(T)
    r = float(r)
    sigma = float(sigma)
    q = float(q)
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    sqrt_t = math.sqrt(T)
    df_r = math.exp(-r * T)
    df_q = math.exp(-q * T)
    phi_d1 = normal_pdf(d1)

    gamma = df_q * phi_d1 / (S * sigma * sqrt_t)
    vega = S * df_q * phi_d1 * sqrt_t

    if cp == "call":
        nd1 = normal_cdf(d1)
        nd2 = normal_cdf(d2)
        delta = df_q * nd1
        theta = (
            -S * df_q * phi_d1 * sigma / (2.0 * sqrt_t)
            - r * K * df_r * nd2
            + q * S * df_q * nd1
        )
        rho = K * T * df_r * nd2
    else:
        nmd1 = normal_cdf(-d1)
        nmd2 = normal_cdf(-d2)
        delta = -df_q * nmd1
        theta = (
            -S * df_q * phi_d1 * sigma / (2.0 * sqrt_t)
            + r * K * df_r * nmd2
            - q * S * df_q * nmd1
        )
        rho = -K * T * df_r * nmd2

    return Greeks(delta=delta, gamma=gamma, vega=vega, theta=theta, rho=rho)


def implied_volatility(
    price: float,
    call_put: str,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float = 0.0,
) -> float:
    """Solve for the volatility implied by a market price (bisection).

    The price is monotonically increasing in ``sigma``, so bisection over
    ``[_IV_LO, _IV_HI]`` is exact. Raises when the price lies outside the
    no-arbitrage bounds of the model — a price below intrinsic or above the
    deep-in-the-money limit has no real volatility.
    """
    _validate_base(call_put, S, K, T)
    cp = _cp(call_put)
    S = float(S)
    K = float(K)
    T = float(T)
    r = float(r)
    q = float(q)
    price = float(price)
    if price <= 0:
        raise ValueError("price must be positive")

    lo_price = black_scholes(cp, S, K, T, r, _IV_LO, q).price
    hi_price = black_scholes(cp, S, K, T, r, _IV_HI, q).price
    if not (lo_price <= price <= hi_price):
        raise ValueError(
            f"price {price} is outside the no-arbitrage bounds "
            f"[{lo_price}, {hi_price}] for this option"
        )

    lo, hi = _IV_LO, _IV_HI
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if black_scholes(cp, S, K, T, r, mid, q).price >= price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0
