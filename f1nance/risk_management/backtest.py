"""VaR backtesting — Kupiec and Christoffersen tests, stdlib-only.

Hermes-independent (``math`` + ``dataclasses``). A VaR *forecast* is a promise:
at confidence ``c``, losses should exceed the VaR no more than ``1 - c`` of the
time. Backtesting checks whether the realized returns kept that promise.

Conventions (matching ``f1nance.portfolio.risk``):

- ``var_forecasts`` are **positive loss numbers** (``0.05`` = a 5% loss
  threshold), one per period, aligned with ``realized_returns``.
- ``realized_returns`` are **signed period returns** (``-0.06`` = a 6% loss).
- An **exception** occurs when the realized loss exceeds the forecast:
  ``realized_returns[i] < -var_forecasts[i]``.
- ``confidence`` is the VaR confidence (default ``0.95`` → expected exception
  rate ``0.05``); ``significance`` is the test's rejection threshold (default
  ``0.05``).

Three likelihood-ratio tests, each with a p-value from the chi-square survival:

- **Kupiec POF** — is the *count* of exceptions consistent with the promised
  rate? (χ² with 1 df.)
- **Christoffersen independence** — are exceptions *clustered* (serially
  dependent)? A VaR that breaches in runs is a broken model even if the total
  count is right. (χ² with 1 df.)
- **Conditional coverage** — the sum of the two, testing rate and clustering
  jointly. (χ² with 2 df.)

Degenerate input raises: empty series, misaligned lengths, a confidence or
significance outside ``(0, 1)``, or a negative VaR forecast (a loss threshold
cannot be negative).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass
class VarBacktest:
    """The result of backtesting a VaR series against realized returns."""

    n: int
    exceptions: int
    exception_rate: float
    expected_rate: float
    confidence: float
    significance: float
    kupiec_lr: float
    kupiec_pvalue: float
    kupiec_reject: bool
    christoffersen_lr: float
    christoffersen_pvalue: float
    christoffersen_reject: bool
    conditional_coverage_lr: float
    conditional_coverage_pvalue: float
    conditional_coverage_reject: bool


def _chi2_sf(x: float, df: int) -> float:
    """Survival function of the chi-square distribution (df 1 or 2 only)."""
    x = float(x)
    if df == 1:
        return math.erfc(math.sqrt(x / 2.0))
    if df == 2:
        return math.exp(-x / 2.0)
    raise ValueError(f"chi-square survival only implemented for df in {{1, 2}}, got {df!r}")


def _kupiec_lr(x: int, n: int, p: float) -> float:
    """Kupiec proportion-of-failures LR statistic, closed form at the edges."""
    if x == 0:
        return -2.0 * n * math.log1p(-p)
    if x == n:
        return -2.0 * n * math.log(p)
    p_hat = x / n
    return -2.0 * (
        (n - x) * math.log((1.0 - p) / (1.0 - p_hat))
        + x * math.log(p / p_hat)
    )


def var_backtest(
    var_forecasts: Sequence[float],
    realized_returns: Sequence[float],
    confidence: float = 0.95,
    significance: float = 0.05,
) -> VarBacktest:
    """Backtest a VaR forecast series against realized returns."""
    forecasts = [float(v) for v in var_forecasts]
    returns = [float(r) for r in realized_returns]
    if not forecasts:
        raise ValueError("cannot backtest an empty VaR series")
    if len(forecasts) != len(returns):
        raise ValueError(
            f"VaR forecasts and realized returns must be aligned: "
            f"{len(forecasts)} vs {len(returns)}"
        )
    if not (0.0 < confidence < 1.0):
        raise ValueError(f"confidence {confidence!r} outside (0, 1)")
    if not (0.0 < significance < 1.0):
        raise ValueError(f"significance {significance!r} outside (0, 1)")
    for i, v in enumerate(forecasts):
        if v < 0:
            raise ValueError(f"VaR forecast at index {i} is negative ({v}); VaR is a loss, must be >= 0")

    n = len(forecasts)
    exceptions = [1 if returns[i] < -forecasts[i] else 0 for i in range(n)]
    x = sum(exceptions)
    p = 1.0 - confidence

    kupiec_lr = max(0.0, _kupiec_lr(x, n, p))
    kupiec_pvalue = _chi2_sf(kupiec_lr, 1)

    # Christoffersen independence — transitions between consecutive states.
    n00 = n01 = n10 = n11 = 0
    for i in range(n - 1):
        prev, cur = exceptions[i], exceptions[i + 1]
        if prev == 0 and cur == 0:
            n00 += 1
        elif prev == 0 and cur == 1:
            n01 += 1
        elif prev == 1 and cur == 0:
            n10 += 1
        else:
            n11 += 1

    if (n00 + n01) == 0 or (n10 + n11) == 0:
        # All one state -> no transitions -> independence holds trivially.
        christoffersen_lr = 0.0
        christoffersen_pvalue = 1.0
    else:
        pi0 = n01 / (n00 + n01)
        pi1 = n11 / (n10 + n11)
        pi = (n01 + n11) / (n00 + n01 + n10 + n11)
        log_restricted = 0.0
        log_full = 0.0
        if (n00 + n10) > 0:
            log_restricted += (n00 + n10) * math.log(1.0 - pi)
        if (n01 + n11) > 0:
            log_restricted += (n01 + n11) * math.log(pi)
        if n00 > 0:
            log_full += n00 * math.log(1.0 - pi0)
        if n01 > 0:
            log_full += n01 * math.log(pi0)
        if n10 > 0:
            log_full += n10 * math.log(1.0 - pi1)
        if n11 > 0:
            log_full += n11 * math.log(pi1)
        christoffersen_lr = max(0.0, -2.0 * (log_restricted - log_full))
        christoffersen_pvalue = _chi2_sf(christoffersen_lr, 1)

    cc_lr = kupiec_lr + christoffersen_lr
    cc_pvalue = _chi2_sf(cc_lr, 2)

    return VarBacktest(
        n=n,
        exceptions=x,
        exception_rate=x / n,
        expected_rate=p,
        confidence=confidence,
        significance=significance,
        kupiec_lr=kupiec_lr,
        kupiec_pvalue=kupiec_pvalue,
        kupiec_reject=kupiec_pvalue < significance,
        christoffersen_lr=christoffersen_lr,
        christoffersen_pvalue=christoffersen_pvalue,
        christoffersen_reject=christoffersen_pvalue < significance,
        conditional_coverage_lr=cc_lr,
        conditional_coverage_pvalue=cc_pvalue,
        conditional_coverage_reject=cc_pvalue < significance,
    )
