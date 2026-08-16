"""F1NANCE derivatives engine — Phase-8 native core.

Hermes-independent, stdlib-only (``math`` + ``dataclasses``). Options pricing
and the risk measures that travel with them. Built on the same guarantee as
the rest of the harness: a number is never *fabricated*. The fixed-income
engine (``f1nance.fixed_income``) supplies the continuous-compounding discount
math this package inherits; this package prices options and refuses to guess
when the input is degenerate.

Two modules:

- ``black_scholes`` — closed-form European pricing, the Greeks
  (delta/gamma/vega/theta/rho), and an implied-volatility solver.
- ``binomial`` — a Cox-Ross-Rubinstein lattice for European and American
  options (early-exercise premium, and the fallback for payoffs Black-Scholes
  cannot price closed-form).
"""

from .binomial import binomial_price
from .black_scholes import (
    Greeks,
    OptionPrice,
    black_scholes,
    greeks,
    implied_volatility,
    normal_cdf,
    normal_pdf,
)

__version__ = "0.1.0"

__all__ = [
    "Greeks",
    "OptionPrice",
    "binomial_price",
    "black_scholes",
    "greeks",
    "implied_volatility",
    "normal_cdf",
    "normal_pdf",
    "__version__",
]
