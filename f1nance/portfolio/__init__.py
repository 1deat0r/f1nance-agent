"""F1NANCE portfolio & risk engine — Phase-2 native core.

Hermes-independent, stdlib-only. Built on top of the ``f1nance.data``
substrate: the data layer guarantees a number is never fabricated, this
package guarantees a portfolio number is never *arithmetically* fabricated.

Three modules:

- ``positions`` — ``Position`` / ``Portfolio``: weights, exposure, FX, cash
  drag, and rebalance trades.
- ``risk`` — returns plus volatility, VaR/CVaR, beta, drawdown, and
  concentration on a returns series.
- ``attribution`` — Brinson-Fachler allocation/selection/interaction.
"""

from .attribution import AttributionResult, AttributionRow, brinson
from .positions import (
    Exposure,
    Holding,
    InvalidPortfolio,
    MissingFxRate,
    Portfolio,
    Position,
    rebalance_trades,
)
from .risk import (
    annualized_return,
    annualized_volatility,
    beta,
    concentration,
    correlation,
    covariance,
    cvar_historical,
    downside_deviation,
    drawdown_series,
    effective_n,
    hhi,
    log_returns,
    max_drawdown,
    returns_from_prices,
    sharpe_ratio,
    simple_returns,
    sortino_ratio,
    var_historical,
    var_parametric,
    volatility,
)

__version__ = "0.1.0"

__all__ = [
    "AttributionResult",
    "AttributionRow",
    "Exposure",
    "Holding",
    "InvalidPortfolio",
    "MissingFxRate",
    "Portfolio",
    "Position",
    "annualized_return",
    "annualized_volatility",
    "beta",
    "brinson",
    "concentration",
    "correlation",
    "covariance",
    "cvar_historical",
    "downside_deviation",
    "drawdown_series",
    "effective_n",
    "hhi",
    "log_returns",
    "max_drawdown",
    "rebalance_trades",
    "returns_from_prices",
    "sharpe_ratio",
    "simple_returns",
    "sortino_ratio",
    "var_historical",
    "var_parametric",
    "volatility",
    "__version__",
]
