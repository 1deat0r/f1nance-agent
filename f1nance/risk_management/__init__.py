"""F1NANCE risk-management engine — Phase-9 native core.

Hermes-independent, stdlib-only (``math`` + ``dataclasses``). This is the
layer that turns "risk first" from a slogan into a checkable contract, on top
of the Phase-2 ``portfolio.risk`` metrics (VaR/CVaR/vol/drawdown/concentration)
and the Phase-8 Greeks (gamma/vega exposure). It never fabricates a number: a
limit whose metric is missing, a stress scenario that shocks nothing, or a
negative VaR forecast all raise rather than producing a plausible-looking
"pass".

Three modules:

- ``limits`` — named risk limits (max/min thresholds) checked against current
  metrics, with breach/headroom/utilization reported.
- ``stress`` — scenario stress testing (linear factor shocks → P&L) and
  reverse stress testing (solve the shock for a target loss).
- ``backtest`` — VaR backtesting: Kupiec proportion-of-failures and
  Christoffersen independence/conditional-coverage tests, each with a p-value.
"""

from .backtest import VarBacktest, var_backtest
from .limits import (
    Limit,
    LimitResult,
    LimitsReport,
    check_limit,
    check_limits,
)
from .stress import (
    ReverseStressResult,
    Scenario,
    StressOutcome,
    reverse_stress,
    stress_test,
)

__version__ = "0.1.0"

__all__ = [
    "Limit",
    "LimitResult",
    "LimitsReport",
    "ReverseStressResult",
    "Scenario",
    "StressOutcome",
    "VarBacktest",
    "check_limit",
    "check_limits",
    "reverse_stress",
    "stress_test",
    "var_backtest",
    "__version__",
]
