"""F1NANCE fixed-income engine — Phase-7 native core.

Hermes-independent, stdlib-only (``math`` + ``dataclasses``). Bonds, yield
curves, and the risk measures that travel with them. Built on the same
guarantee as the rest of the harness: a number is never *fabricated*. The
data layer (``f1nance.data``) supplies the inputs (FRED treasury yields via
``get_macro_series``); this package supplies the arithmetic and refuses to
guess when the input is degenerate.

Three modules:

- ``curves`` — discount factors, spot/forward rates, present value, and
  par→spot bootstrapping.
- ``bonds`` — clean-price bond pricing, yield-to-maturity, and the risk
  measures (Macaulay / modified duration, convexity, DV01).
- ``cli`` — ``python -m f1nance.fixed_income`` with JSON output.
"""

from .bonds import BondRisk, bond_price, cashflows, duration_and_convexity, ytm
from .curves import (
    bootstrap_spot_curve,
    discount_factor,
    forward_rate,
    interpolate_spot,
    pv,
    pv_curve,
    spot_rate,
)

__version__ = "0.1.0"

__all__ = [
    "BondRisk",
    "bond_price",
    "bootstrap_spot_curve",
    "cashflows",
    "discount_factor",
    "duration_and_convexity",
    "forward_rate",
    "interpolate_spot",
    "pv",
    "pv_curve",
    "spot_rate",
    "ytm",
    "__version__",
]
