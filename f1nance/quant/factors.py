"""Factor construction and exposure models — stdlib-only, no overfit theater.

Hermes-independent by design: ``math`` + ``statistics`` + the local
``f1nance.quant.linear`` OLS. Built on the data and portfolio layers: the
numbers you regress come from the data substrate, and the risk vocabulary
(vol, Sharpe, drawdown) lives in ``f1nance.portfolio``.

Contents:

- ``capm`` — single-factor regression of excess asset returns on excess market
  returns: alpha (the claimed skill) and beta (the market exposure).
- ``multi_factor`` — excess asset returns on a set of factor excess returns
  (Fama-French / Carhart style): an exposure per factor plus residual risk.
- ``cross_sectional_zscore`` / ``cross_sectional_rank`` — per-date
  cross-sectional standardization / percentile ranking, for building factors
  that are comparable across the universe.
- ``trailing_return`` / ``momentum_predictor`` — the momentum factor and a
  point-in-time predictor for the ``f1nance.quant.backtest`` harness.

Conventions:

- Returns are period returns in decimal form (``0.01`` = +1%).
- Excess returns subtract the *per-period* risk-free rate
  (``risk_free_rate / periods_per_year``).
- ``annualized_alpha = alpha * periods_per_year`` (arithmetic).
- Degenerate input raises: mismatched series, too few observations, a
  cross-section with zero variance, ``top_k`` beyond the universe.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from .linear import ols


@dataclass
class FactorModelResult:
    """Exposure decomposition of an asset's excess returns.

    ``alpha`` is the intercept — the part of return NOT explained by the
    factors, i.e. the thing you claim is skill. ``exposures`` maps each factor
    name to its beta. ``exposure_t_statistics`` entries are ``None`` when a
    coefficient is perfectly identified.
    """

    alpha: float
    annualized_alpha: float
    exposures: Dict[str, float]
    exposure_standard_errors: Dict[str, float]
    exposure_t_statistics: Dict[str, Optional[float]]
    r_squared: float
    residual_volatility: float  # per-period stddev of residuals (idiosyncratic risk)
    n_observations: int
    n_factors: int


def _factor_fit(
    y: Sequence[float],
    factor_columns: Sequence[Sequence[float]],
    factor_names: Sequence[str],
    periods_per_year: int,
    n_observations: int,
) -> FactorModelResult:
    reg = ols(y, list(factor_columns), fit_intercept=True, feature_names=list(factor_names))
    alpha = reg.coefficients[0]
    exposures = {name: reg.coefficients[1 + i] for i, name in enumerate(factor_names)}
    se = {name: reg.standard_errors[1 + i] for i, name in enumerate(factor_names)}
    t = {name: reg.t_statistics[1 + i] for i, name in enumerate(factor_names)}
    return FactorModelResult(
        alpha=alpha,
        annualized_alpha=alpha * periods_per_year,
        exposures=exposures,
        exposure_standard_errors=se,
        exposure_t_statistics=t,
        r_squared=reg.r_squared,
        residual_volatility=statistics.pstdev(reg.residuals),
        n_observations=n_observations,
        n_factors=len(factor_names),
    )


def capm(
    asset_returns: Sequence[float],
    market_returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> FactorModelResult:
    """Single-factor CAPM: ``R_i − rf = α + β(R_m − rf) + ε``.

    Returns alpha (per-period), annualized alpha, beta, its standard error and
    t-statistic, R², and residual (idiosyncratic) volatility.
    """
    n = len(asset_returns)
    if len(market_returns) != n:
        raise ValueError("asset and market series must be the same length")
    if n < 3:
        raise ValueError("CAPM regression needs at least 3 observations")
    rf_per = risk_free_rate / periods_per_year
    y = [r - rf_per for r in asset_returns]
    x = [r - rf_per for r in market_returns]
    return _factor_fit(y, [x], ["market"], periods_per_year, n)


def multi_factor(
    asset_returns: Sequence[float],
    factor_returns: Dict[str, Sequence[float]],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> FactorModelResult:
    """Multi-factor regression of excess asset returns on factor excess returns.

    ``factor_returns`` maps factor name -> returns series (e.g. ``MKT``,
    ``SMB``, ``HML``, ``UMD``). A strategy that "beats the market" but loads
    heavily on SMB/HML has factor exposure, not alpha. This is how you tell.
    """
    n = len(asset_returns)
    if not factor_returns:
        raise ValueError("multi_factor requires at least one factor")
    factor_names = sorted(factor_returns.keys())  # deterministic order
    for name in factor_names:
        if len(factor_returns[name]) != n:
            raise ValueError(f"factor {name!r} length mismatch")
    rf_per = risk_free_rate / periods_per_year
    y = [r - rf_per for r in asset_returns]
    columns = [[r - rf_per for r in factor_returns[name]] for name in factor_names]
    return _factor_fit(y, columns, factor_names, periods_per_year, n)


# --- cross-sectional factor construction ------------------------------------

def _row_keys(rows: Sequence[Dict[str, float]]) -> List[str]:
    keys: Optional[List[str]] = None
    for row in rows:
        k = sorted(row.keys())
        if keys is None:
            keys = k
        elif k != keys:
            raise ValueError("all rows must share the same assets")
    return keys or []


def cross_sectional_zscore(rows: Sequence[Dict[str, float]]) -> List[Dict[str, float]]:
    """Standardize each date's values across assets (population stddev).

    ``rows`` is one dict per date, ``asset -> value``. Returns the same shape
    with each date's values replaced by ``(x − mean) / σ``. A date with zero
    cross-sectional variance raises — the z-score is genuinely undefined there.
    """
    out: List[Dict[str, float]] = []
    keys = _row_keys(rows)
    for row in rows:
        values = [row[k] for k in keys]
        if len(values) < 2:
            raise ValueError("cross-sectional z-score needs at least two assets")
        sd = statistics.pstdev(values)
        if sd == 0.0:
            raise ValueError("cross-sectional z-score undefined when all assets are equal")
        mean = statistics.fmean(values)
        out.append({k: (row[k] - mean) / sd for k in keys})
    return out


def _percentile_rank(values: Sequence[float]) -> List[float]:
    """0..1 percentile rank of each value (ties averaged), ascending."""
    n = len(values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0
        pct = avg / (n - 1) if n > 1 else 0.0
        for k in range(i, j + 1):
            ranks[order[k]] = pct
        i = j + 1
    return ranks


def cross_sectional_rank(rows: Sequence[Dict[str, float]]) -> List[Dict[str, float]]:
    """Per-date cross-sectional percentile rank (0 = bottom, 1 = top).

    Ties are averaged. Useful for turning a noisy raw factor into a bounded,
    comparable score before portfolio construction.
    """
    keys = _row_keys(rows)
    out: List[Dict[str, float]] = []
    for row in rows:
        values = [row[k] for k in keys]
        pcts = _percentile_rank(values)
        out.append({k: pcts[i] for i, k in enumerate(keys)})
    return out


# --- momentum ---------------------------------------------------------------

def trailing_return(returns: Sequence[float], lookback: int) -> float:
    """Compounded return over the trailing ``lookback`` periods.

    ``∏(1 + r) − 1`` over ``returns[-lookback:]`` — the classic momentum
    signal. Uses only the end of the series, so feeding it point-in-time data
    keeps it look-ahead free.
    """
    if lookback < 1:
        raise ValueError("lookback must be at least 1")
    if len(returns) < lookback:
        raise ValueError(f"need at least {lookback} returns, have {len(returns)}")
    growth = 1.0
    for r in returns[-lookback:]:
        growth *= 1.0 + r
    return growth - 1.0


def momentum_predictor(lookback: int, top_k: int) -> Callable[[Dict[str, List[float]]], Dict[str, float]]:
    """Build a point-in-time momentum predictor for ``backtest.walk_forward``.

    The returned callable takes ``history`` (asset -> returns through the
    decision date) and returns equal-weight holdings across the ``top_k`` assets
    with the highest trailing ``lookback``-period return. It only reads the tail
    of ``history``, so as long as the harness hands it point-in-time data the
    signal cannot see the future.
    """
    if lookback < 1:
        raise ValueError("lookback must be at least 1")
    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    def predict(history: Dict[str, List[float]]) -> Dict[str, float]:
        assets = sorted(history.keys())
        if not assets:
            raise ValueError("no assets in history")
        if top_k > len(assets):
            raise ValueError(f"top_k ({top_k}) exceeds the number of assets ({len(assets)})")
        scores = {a: trailing_return(history[a], lookback) for a in assets}
        ranked = sorted(assets, key=lambda a: scores[a], reverse=True)
        top = set(ranked[:top_k])
        weight = 1.0 / top_k
        return {a: (weight if a in top else 0.0) for a in assets}

    return predict
