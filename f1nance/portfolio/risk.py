"""Risk metrics on a returns series — stdlib-only, no fabricated numbers.

Hermes-independent by design: ``math`` + ``statistics`` only. Every metric here
is defined on a chronological sequence of returns (or prices, from which
returns are derived). Inputs are floats in decimal form (0.05 = 5%).

Conventions (read before trusting a number out):

- **Returns are period returns.** ``0.01`` means +1% over one period. Periodic
  metrics (volatility, VaR, CVaR) are per-period; annualized metrics scale by
  ``periods_per_year`` (default 252, daily).
- **Stddev is population (ddof=0), matching numpy's ``np.std`` default.** A
  full return history is treated as the population being measured.
- **Drawdown is quoted as a positive magnitude.** ``max_drawdown`` returns
  ``0.20`` for a 20% peak-to-trough decline. ``drawdown_series`` returns the
  signed series (``<= 0``), from which the max is derived.
- **VaR/CVaR are positive loss numbers.** ``var_historical`` returns ``0.05``
  for a 5% loss at the chosen confidence. ``cvar_historical`` is the mean of
  returns at or beyond that threshold (expected shortfall).
- **Degenerate inputs raise.** Empty returns, zero variance (beta, Sharpe),
  and mismatched series lengths (beta, correlation) raise ``ValueError`` rather
  than returning a misleading 0 or inf.
"""

from __future__ import annotations

import math
import statistics
from typing import Iterable, List, Optional, Sequence


def simple_returns(prices: Sequence[float]) -> List[float]:
    """Period-over-period simple returns: ``p_t / p_{t-1} - 1``."""
    return [b / a - 1.0 for a, b in zip(prices, prices[1:])]


def log_returns(prices: Sequence[float]) -> List[float]:
    """Continuously-compounded returns: ``ln(p_t / p_{t-1})``."""
    out: List[float] = []
    for a, b in zip(prices, prices[1:]):
        if a <= 0 or b <= 0:
            raise ValueError("log returns require strictly positive prices")
        out.append(math.log(b / a))
    return out


def returns_from_prices(prices: Sequence[float], method: str = "simple") -> List[float]:
    """Returns from a price series; ``method`` is ``"simple"`` or ``"log"``."""
    if method == "simple":
        return simple_returns(prices)
    if method == "log":
        return log_returns(prices)
    raise ValueError(f"unknown return method {method!r}")


def _require_returns(returns: Sequence[float]) -> None:
    if len(returns) == 0:
        raise ValueError("cannot compute a metric on an empty returns series")


# --- return / volatility ----------------------------------------------------

def annualized_return(
    returns: Sequence[float],
    periods_per_year: int = 252,
    geometric: bool = True,
) -> float:
    """Annualized return. Geometric (compound) by default, arithmetic otherwise."""
    _require_returns(returns)
    if geometric:
        growth = 1.0
        for r in returns:
            growth *= 1.0 + r
        if growth <= 0:
            return -1.0
        return growth ** (periods_per_year / len(returns)) - 1.0
    return statistics.fmean(returns) * periods_per_year


def volatility(returns: Sequence[float]) -> float:
    """Per-period volatility (population stddev)."""
    _require_returns(returns)
    if len(returns) < 2:
        raise ValueError("volatility requires at least two returns")
    return statistics.pstdev(returns)


def annualized_volatility(returns: Sequence[float], periods_per_year: int = 252) -> float:
    """Annualized volatility: ``σ · sqrt(periods_per_year)``."""
    return volatility(returns) * math.sqrt(periods_per_year)


def sharpe_ratio(
    returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Annualized Sharpe: ``√n · mean(r - rf/n) / σ``.

    ``risk_free_rate`` is annual. A zero-volatility series has an undefined
    Sharpe and raises.
    """
    _require_returns(returns)
    rf_per = risk_free_rate / periods_per_year
    mean_excess = statistics.fmean(r - rf_per for r in returns)
    sd = volatility(returns)
    if sd == 0.0:
        raise ValueError("Sharpe ratio is undefined when volatility is zero")
    return math.sqrt(periods_per_year) * mean_excess / sd


def downside_deviation(returns: Sequence[float], target: float = 0.0) -> float:
    """Root-mean-square of returns below ``target`` (per-period MAR)."""
    _require_returns(returns)
    if len(returns) < 2:
        raise ValueError("downside deviation requires at least two returns")
    below = [min(r - target, 0.0) ** 2 for r in returns]
    return math.sqrt(statistics.fmean(below))


def sortino_ratio(
    returns: Sequence[float],
    target: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Annualized Sortino: ``√n · mean(r - target) / downside_deviation``."""
    _require_returns(returns)
    mean_excess = statistics.fmean(r - target for r in returns)
    dd = downside_deviation(returns, target)
    if dd == 0.0:
        raise ValueError("Sortino ratio is undefined when downside deviation is zero")
    return math.sqrt(periods_per_year) * mean_excess / dd


# --- drawdown ---------------------------------------------------------------

def drawdown_series(prices: Sequence[float]) -> List[float]:
    """Signed drawdown series: ``p_t / running_peak - 1`` (<= 0)."""
    if not prices:
        return []
    peak = prices[0]
    out: List[float] = []
    for p in prices:
        peak = max(peak, p)
        out.append(p / peak - 1.0 if peak else 0.0)
    return out


def max_drawdown(prices: Sequence[float]) -> float:
    """Largest peak-to-trough decline as a positive magnitude (0.20 = 20%)."""
    dd = drawdown_series(prices)
    if not dd:
        return 0.0
    return -min(dd)


# --- tail risk --------------------------------------------------------------

def _percentile(sorted_values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile of an ascending-sorted sequence; ``q`` in [0, 1]."""
    n = len(sorted_values)
    if n == 0:
        raise ValueError("cannot take a percentile of an empty sequence")
    if not (0.0 <= q <= 1.0):
        raise ValueError(f"quantile {q!r} outside [0, 1]")
    rank = max(1, min(n, int(math.ceil(q * n))))
    return sorted_values[rank - 1]


def var_historical(returns: Sequence[float], confidence: float = 0.95) -> float:
    """Historical VaR: the loss (positive) at the (1 - confidence) quantile."""
    _require_returns(returns)
    if not (0.0 < confidence < 1.0):
        raise ValueError(f"confidence {confidence!r} outside (0, 1)")
    threshold = _percentile(sorted(returns), 1.0 - confidence)
    return -threshold


def cvar_historical(returns: Sequence[float], confidence: float = 0.95) -> float:
    """Historical CVaR (expected shortfall): mean loss beyond the VaR threshold."""
    _require_returns(returns)
    if not (0.0 < confidence < 1.0):
        raise ValueError(f"confidence {confidence!r} outside (0, 1)")
    threshold = _percentile(sorted(returns), 1.0 - confidence)
    tail = [r for r in returns if r <= threshold]
    return -statistics.fmean(tail)


def var_parametric(
    returns: Sequence[float],
    confidence: float = 0.95,
    periods_per_year: int = 252,
) -> float:
    """Parametric (normal) annualized VaR: ``z · σ · sqrt(periods_per_year)``.

    Uses the normal inverse-CDF via the stdlib ``math`` (an approximation is
    not used — ``statistics.NormalDist`` provides ``inv_cdf`` exactly).
    """
    _require_returns(returns)
    if not (0.0 < confidence < 1.0):
        raise ValueError(f"confidence {confidence!r} outside (0, 1)")
    z = statistics.NormalDist().inv_cdf(confidence)
    return z * annualized_volatility(returns, periods_per_year)


# --- relative risk ----------------------------------------------------------

def _aligned(returns: Sequence[float], benchmark_returns: Sequence[float]) -> None:
    if len(returns) != len(benchmark_returns):
        raise ValueError(
            f"series lengths differ: {len(returns)} vs {len(benchmark_returns)}"
        )
    if len(returns) < 2:
        raise ValueError("at least two paired observations are required")


def covariance(returns: Sequence[float], benchmark_returns: Sequence[float]) -> float:
    """Population covariance of two equal-length series."""
    _aligned(returns, benchmark_returns)
    n = len(returns)
    mean_r = statistics.fmean(returns)
    mean_b = statistics.fmean(benchmark_returns)
    return sum((r - mean_r) * (b - mean_b) for r, b in zip(returns, benchmark_returns)) / n


def beta(returns: Sequence[float], benchmark_returns: Sequence[float]) -> float:
    """Beta of ``returns`` vs ``benchmark_returns``: cov / var(benchmark)."""
    _aligned(returns, benchmark_returns)
    var_b = statistics.pvariance(benchmark_returns)
    if var_b == 0.0:
        raise ValueError("beta is undefined when the benchmark has zero variance")
    return covariance(returns, benchmark_returns) / var_b


def correlation(returns: Sequence[float], benchmark_returns: Sequence[float]) -> float:
    """Pearson correlation of two equal-length series."""
    _aligned(returns, benchmark_returns)
    sd_r = statistics.pstdev(returns)
    sd_b = statistics.pstdev(benchmark_returns)
    if sd_r == 0.0 or sd_b == 0.0:
        raise ValueError("correlation is undefined when either series has zero variance")
    return covariance(returns, benchmark_returns) / (sd_r * sd_b)


# --- concentration ----------------------------------------------------------

def hhi(weights: Iterable[float]) -> float:
    """Herfindahl-Hirschman index: sum of squared weights (1 = one position)."""
    return sum(w * w for w in weights)


def effective_n(weights: Iterable[float]) -> float:
    """Effective number of positions: ``1 / HHI`` (equal-weight == N)."""
    h = hhi(weights)
    return 1.0 / h if h > 0 else 0.0


def concentration(weights: Iterable[float]) -> dict:
    """HHI, effective N, and the largest single and top-3 weights."""
    w = sorted((x for x in weights if x > 0), reverse=True)
    return {
        "hhi": hhi(w),
        "effective_n": effective_n(w),
        "top_weight": w[0] if w else 0.0,
        "top3_weight": sum(w[:3]),
    }
