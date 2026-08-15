"""F1NANCE quant & backtesting engine — Phase-3 native core.

Hermes-independent, stdlib-only. Built on top of the ``f1nance.data`` and
``f1nance.portfolio`` layers: the data layer guarantees a number is never
fabricated, the portfolio layer guarantees a risk number is never
*arithmetically* fabricated, and this package guarantees a backtest is never
*statistically* fabricated — point-in-time signals only, explicit costs, and a
strict separation of in-sample (look-ahead) from out-of-sample results.

Three modules:

- ``linear`` — OLS / ridge regression and the minimal linear algebra they need.
- ``factors`` — CAPM and multi-factor exposure models, cross-sectional factor
  construction (z-score / rank), and the momentum factor.
- ``backtest`` — a walk-forward backtesting harness with transaction costs,
  look-ahead guards, and honest in-sample / out-of-sample reporting.
"""

from .backtest import (
    BacktestResult,
    WalkForwardResult,
    backtest_weights,
    validate_aligned,
    walk_forward,
)
from .factors import (
    FactorModelResult,
    capm,
    cross_sectional_rank,
    cross_sectional_zscore,
    momentum_predictor,
    multi_factor,
    trailing_return,
)
from .linear import RegressionResult, ols, ridge

__version__ = "0.1.0"

__all__ = [
    "BacktestResult",
    "FactorModelResult",
    "RegressionResult",
    "WalkForwardResult",
    "backtest_weights",
    "capm",
    "cross_sectional_rank",
    "cross_sectional_zscore",
    "momentum_predictor",
    "multi_factor",
    "ols",
    "ridge",
    "trailing_return",
    "validate_aligned",
    "walk_forward",
    "__version__",
]
