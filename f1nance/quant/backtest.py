"""Backtesting harness — walk-forward, costs, look-ahead guards, honest IS/OOS.

Hermes-independent by design: stdlib + ``f1nance.portfolio.risk`` for the
performance vocabulary. The harness does not decide what to trade — it turns a
point-in-time *predictor* into an honest performance record.

The non-negotiables:

- **Point-in-time only.** ``walk_forward`` hands the predictor ONLY the data
  available up to the decision date. A predictor that wants tomorrow's return
  must reach outside the harness to get it — the harness will not hand it over.
- **Costs are explicit.** Turnover × (cost_bps + slippage_bps) is subtracted
  every period, including the initial deployment from cash. A strategy that is
  positive gross but negative net is reported net.
- **In-sample and out-of-sample are never conflated.** The in-sample record is
  computed with full-sample look-ahead and flagged ``lookahead=True`` — it is
  the "would have looked great" number, not a result.
- **Degenerate input raises.** Mismatched series, weights that don't sum to 1.0,
  a held asset with no return, a ``min_train`` that leaves no holdout — all
  raise rather than fabricate.

Conventions:

- History is a dict ``asset -> list[float]`` of *period returns*, aligned and
  chronological.
- A predictor is ``callable(history) -> dict[asset -> weight]`` producing the
  target weights for the *next* period; weights must sum to 1.0 (a long-only
  book; shorts push weights negative and are summed in absolute-value turnover).
- Turnover is ``Σ |Δweight|`` per period; the first period counts a full
  deployment (turnover 1.0 from cash).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from f1nance.portfolio.risk import (
    annualized_return,
    annualized_volatility,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)

_W_TOL = 1e-9


@dataclass
class BacktestResult:
    """A completed backtest run (one equity curve + performance record)."""

    equity_curve: List[float]            # NAV multiples, starts at 1.0
    returns: List[float]                 # net-of-cost period returns
    turnover: List[float]                # per-period turnover (sum |Δw|)
    n_periods: int
    total_return: float                  # equity[-1] - 1
    annualized_return: Optional[float]   # geometric CAGR
    annualized_volatility: Optional[float]
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    max_drawdown: float                  # positive magnitude (0.20 = 20%)
    hit_rate: float                      # fraction of positive periods
    mean_turnover: float
    total_cost: float                    # sum of per-period cost drags (return units)
    lookahead: bool = False              # True ONLY for the in-sample baseline


@dataclass
class WalkForwardResult:
    """Walk-forward validation: the honest record plus the leaky baseline."""

    out_of_sample: BacktestResult       # point-in-time; this is the result
    in_sample: BacktestResult           # full-sample look-ahead (lookahead=True)
    min_train: int
    window: Optional[int]               # None = expanding, int = rolling length
    n_forecasts: int                    # number of out-of-sample periods


# --- validation -------------------------------------------------------------

def validate_aligned(series_map: Dict[str, List[float]]) -> int:
    """Return the shared length of every series, raising on empty/mismatch."""
    if not series_map:
        raise ValueError("no series provided")
    lengths = {len(v) for v in series_map.values()}
    if len(lengths) != 1:
        raise ValueError(f"series lengths differ: {sorted(lengths)}")
    n = lengths.pop()
    if n == 0:
        raise ValueError("series are empty")
    return n


def _validate_weights(weights: Dict[str, float]) -> None:
    total = sum(weights.values())
    if abs(total - 1.0) > _W_TOL:
        raise ValueError(f"target weights sum to {total}, not 1.0")


# --- core -------------------------------------------------------------------

def _backtest(
    weights: List[Dict[str, float]],
    period_returns: List[Dict[str, float]],
    cost_bps: float,
    slippage_bps: float,
    periods_per_year: int,
    lookahead: bool,
) -> BacktestResult:
    if not weights:
        raise ValueError("backtest requires at least one period")
    if len(weights) != len(period_returns):
        raise ValueError(
            f"weights has {len(weights)} periods but returns have {len(period_returns)}"
        )
    cost_per_unit = (cost_bps + slippage_bps) / 10000.0
    if cost_per_unit < 0:
        raise ValueError("costs cannot be negative")

    nav = 1.0
    equity = [1.0]
    strat_returns: List[float] = []
    turnover: List[float] = []
    prev: Dict[str, float] = {}
    total_cost = 0.0

    for w, pr in zip(weights, period_returns):
        _validate_weights(w)
        for asset, wt in w.items():
            if wt != 0.0 and asset not in pr:
                raise ValueError(f"no return for held asset {asset!r} at this period")
        gross = sum(wt * pr.get(asset, 0.0) for asset, wt in w.items())
        delta = 0.0
        for asset in set(w) | set(prev):
            delta += abs(w.get(asset, 0.0) - prev.get(asset, 0.0))
        cost = delta * cost_per_unit
        net = gross - cost
        total_cost += cost
        nav *= 1.0 + net
        equity.append(nav)
        strat_returns.append(net)
        turnover.append(delta)
        prev = dict(w)

    return _build_result(equity, strat_returns, turnover, total_cost, periods_per_year, lookahead)


def _build_result(
    equity: List[float],
    returns: List[float],
    turnover: List[float],
    total_cost: float,
    periods_per_year: int,
    lookahead: bool,
) -> BacktestResult:
    n = len(returns)
    total_return = equity[-1] - 1.0

    def _opt(fn):
        try:
            return fn()
        except ValueError:
            return None

    cagr = _opt(lambda: annualized_return(returns, periods_per_year, geometric=True))
    ann_vol = _opt(lambda: annualized_volatility(returns, periods_per_year))
    sharpe = _opt(lambda: sharpe_ratio(returns, 0.0, periods_per_year))
    sortino = _opt(lambda: sortino_ratio(returns, 0.0, periods_per_year))
    mdd = max_drawdown(equity) if len(equity) > 1 else 0.0
    hit = sum(1 for r in returns if r > 0) / n if n else 0.0
    mean_turnover = statistics.fmean(turnover) if turnover else 0.0

    return BacktestResult(
        equity_curve=equity,
        returns=returns,
        turnover=turnover,
        n_periods=n,
        total_return=total_return,
        annualized_return=cagr,
        annualized_volatility=ann_vol,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown=mdd,
        hit_rate=hit,
        mean_turnover=mean_turnover,
        total_cost=total_cost,
        lookahead=lookahead,
    )


def backtest_weights(
    weights: List[Dict[str, float]],
    returns: Dict[str, List[float]],
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
    periods_per_year: int = 252,
    lookahead: bool = False,
) -> BacktestResult:
    """Backtest a supplied sequence of target weights against asset returns.

    ``weights`` is one dict per period (``asset -> weight``, sum to 1.0);
    ``returns`` is ``asset -> aligned list of period returns``. Costs (bps)
    are charged on turnover each period, including initial deployment.
    """
    n = validate_aligned(returns)
    if len(weights) != n:
        raise ValueError(f"weights has {len(weights)} periods but returns have {n}")
    period_returns = [{a: r[i] for a, r in returns.items()} for i in range(n)]
    return _backtest(weights, period_returns, cost_bps, slippage_bps, periods_per_year, lookahead)


# --- walk-forward -----------------------------------------------------------

def _in_sample_backtest(
    history: Dict[str, List[float]],
    predictor: Callable[[Dict[str, List[float]]], Dict[str, float]],
    cost_bps: float,
    slippage_bps: float,
    periods_per_year: int,
) -> BacktestResult:
    """Leaky baseline: the predictor sees the FULL history at every decision date.

    This is the "fit on everything, then evaluate everywhere" number that
    flatters a model. It is flagged ``lookahead=True`` and reported only for
    contrast with the honest out-of-sample record.
    """
    n = validate_aligned(history)
    weights: List[Dict[str, float]] = []
    period_returns: List[Dict[str, float]] = []
    for t in range(n):
        w = predictor(history)  # full-sample look-ahead by construction
        _validate_weights(w)
        weights.append(w)
        period_returns.append({a: r[t] for a, r in history.items()})
    return _backtest(weights, period_returns, cost_bps, slippage_bps, periods_per_year, lookahead=True)


def walk_forward(
    history: Dict[str, List[float]],
    predictor: Callable[[Dict[str, List[float]]], Dict[str, float]],
    min_train: int,
    window: Optional[int] = None,
    step: int = 1,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
    periods_per_year: int = 252,
) -> WalkForwardResult:
    """Rolling-origin walk-forward validation with a strictly point-in-time fit.

    At each out-of-sample period ``t >= min_train`` the predictor receives only
    the data through ``t - 1`` (expanding by default, or a rolling ``window``)
    and returns weights for period ``t``. Those weights are collected into one
    out-of-sample backtest. The in-sample baseline is also computed (full-sample
    look-ahead) and flagged.

    ``step`` re-fits every ``step`` periods (default 1 = classic walk-forward).
    """
    n = validate_aligned(history)
    if min_train < 2:
        raise ValueError("min_train must be at least 2")
    if min_train >= n:
        raise ValueError("min_train must leave at least one out-of-sample period")
    if step < 1:
        raise ValueError("step must be at least 1")
    if window is not None and window < 2:
        raise ValueError("window must be at least 2 when set")

    weights: List[Dict[str, float]] = []
    period_returns: List[Dict[str, float]] = []
    for t in range(min_train, n, step):
        if window is None:
            train = {a: r[:t] for a, r in history.items()}
        else:
            start = max(0, t - window)
            train = {a: r[start:t] for a, r in history.items()}
        w = predictor(train)
        _validate_weights(w)
        weights.append(w)
        period_returns.append({a: r[t] for a, r in history.items()})

    if not weights:
        raise ValueError("walk-forward produced no out-of-sample periods")

    oos = _backtest(weights, period_returns, cost_bps, slippage_bps, periods_per_year, lookahead=False)
    in_sample = _in_sample_backtest(history, predictor, cost_bps, slippage_bps, periods_per_year)
    return WalkForwardResult(
        out_of_sample=oos,
        in_sample=in_sample,
        min_train=min_train,
        window=window,
        n_forecasts=len(weights),
    )
