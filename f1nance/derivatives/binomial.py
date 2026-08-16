"""Cox-Ross-Rubinstein binomial tree for European and American options.

Hermes-independent, stdlib-only. The lattice half of the derivatives engine:
a recombining CRR tree that values both European (exercise at expiry only) and
American (early exercise at every node) options. It is the honest fallback
for the payoffs Black-Scholes cannot price closed-form — American puts, and
(with a few more nodes in the payload) any payoff that fits a lattice.

Conventions match :mod:`f1nance.derivatives.black_scholes`: ``S``/``K``/price
share a currency, ``T`` is years, ``r``/``q``/``sigma`` are annualized decimal
under continuous compounding.

The tree:

- ``dt = T / steps``, ``u = exp(sigma * sqrt(dt))``, ``d = 1 / u``.
- Risk-neutral probability ``p = (exp((r - q) dt) - d) / (u - d)``.
- Backward induction with per-step discount ``exp(-r dt)``; an American node
  takes ``max(hold, exercise)`` at every step, a European node only at expiry.

Degenerate input raises: non-positive spot/strike/time/volatility, ``steps <
1``, and a parameter combination whose risk-neutral probability leaves
``[0, 1]`` (the tree would arbitrage). The European price converges to
Black-Scholes as ``steps`` grows — the test suite asserts that convergence.
"""

from __future__ import annotations

import math

from .black_scholes import _cp, _validate


def binomial_price(
    call_put: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    steps: int = 200,
    american: bool = False,
) -> float:
    """CRR binomial price of a European (default) or American option."""
    _validate(S, K, T, sigma, call_put)
    cp = _cp(call_put)
    S = float(S)
    K = float(K)
    T = float(T)
    r = float(r)
    sigma = float(sigma)
    q = float(q)
    steps = int(steps)
    if steps < 1:
        raise ValueError("steps must be at least 1")

    dt = T / steps
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    a = math.exp((r - q) * dt)
    p = (a - d) / (u - d)
    if not (0.0 <= p <= 1.0):
        raise ValueError(
            f"risk-neutral probability p={p} outside [0, 1] for these "
            "parameters — the tree would arbitrage (sigma too small or "
            "rate/dividend too extreme for the step count)"
        )
    disc = math.exp(-r * dt)

    def payoff(spot: float) -> float:
        return max(spot - K, 0.0) if cp == "call" else max(K - spot, 0.0)

    # terminal values at step `steps`, indexed by up-move count j in 0..steps
    values = [payoff(S * u ** j * d ** (steps - j)) for j in range(steps + 1)]
    for i in range(steps - 1, -1, -1):
        for j in range(i + 1):
            spot = S * u ** j * d ** (i - j)
            hold = disc * (p * values[j + 1] + (1.0 - p) * values[j])
            values[j] = max(hold, payoff(spot)) if american else hold
    return values[0]
