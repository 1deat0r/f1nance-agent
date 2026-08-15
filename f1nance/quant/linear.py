"""Minimal linear algebra + regression — stdlib-only, no fabricated fits.

Hermes-independent by design: ``math`` + ``statistics`` only, no numpy, no
scipy. This is the shared math underneath ``f1nance.quant.factors`` (CAPM and
multi-factor regressions) and anywhere else a least-squares fit is needed.

What is here:

- Gaussian elimination with partial pivoting to solve ``A x = b`` and to
  invert the (symmetric positive-definite) ``XᵀX`` matrix for coefficient
  standard errors.
- Ordinary least squares with an intercept and full inference: coefficients,
  standard errors, t-statistics, R² / adjusted R², residual stddev.
- Ridge regression (L2-regularized least squares) for the "regularize rather
  than overfit" discipline.

What is deliberately NOT here:

- **p-values.** A Student-t CDF (for p-values) and the L1 path solver (Lasso)
  are scipy territory. The quant discipline says economic plausibility over
  ``p < 0.05``, so t-statistics and standard errors are reported and p-values
  are left to a stats package rather than approximated badly.
- **Silent singular fits.** A singular (collinear) design matrix raises
  ``ValueError`` instead of returning a garbage coefficient vector.

Conventions:

- **``y``** is the response (a list of floats, length ``n``).
- **``X``** is a list of *feature columns*, each a list of length ``n``.
  ``fit_intercept=True`` (default) prepends an intercept column.
- **Degenerate input raises**: empty response, feature/response length
  mismatch, fewer observations than parameters, a constant response (R² is
  undefined), or a collinear design.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

_EPS = 1e-12


# --- linear algebra ---------------------------------------------------------

def _solve(a: Sequence[Sequence[float]], b: Sequence[float]) -> List[float]:
    """Solve ``a x = b`` via Gauss-Jordan elimination with partial pivoting.

    ``a`` must be square. Raises ``ValueError`` on a singular matrix — the
    caller's signal that the design is collinear.
    """
    n = len(a)
    if n == 0 or len(b) != n:
        raise ValueError("solve requires a square system with matching rhs")
    m = [list(row) + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < _EPS:
            raise ValueError("singular matrix: collinear regressors or zero-variance feature")
        m[col], m[pivot] = m[pivot], m[col]
        pv = m[col][col]
        m[col] = [x / pv for x in m[col]]
        for r in range(n):
            if r == col:
                continue
            factor = m[r][col]
            m[r] = [m[r][c] - factor * m[col][c] for c in range(n + 1)]
    return [m[i][n] for i in range(n)]


def _invert(a: Sequence[Sequence[float]]) -> List[List[float]]:
    """Invert a square matrix via Gauss-Jordan elimination (partial pivoting)."""
    n = len(a)
    m = [list(row) + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < _EPS:
            raise ValueError("singular matrix: cannot invert (collinear regressors?)")
        m[col], m[pivot] = m[pivot], m[col]
        pv = m[col][col]
        m[col] = [x / pv for x in m[col]]
        for r in range(n):
            if r == col:
                continue
            factor = m[r][col]
            m[r] = [m[r][c] - factor * m[col][c] for c in range(2 * n)]
    return [row[n:] for row in m]


# --- regression result ------------------------------------------------------

@dataclass
class RegressionResult:
    """Output of ``ols`` / ``ridge``.

    ``coefficients`` includes the intercept first (when ``fit_intercept``),
    matching ``feature_names``. ``t_statistics`` entries are ``None`` when the
    standard error is zero (a perfectly-identified coefficient); they are empty
    for ridge, whose OLS-style inference is not meaningful.
    """

    coefficients: List[float]
    standard_errors: List[float]
    t_statistics: List[Optional[float]]
    residuals: List[float]
    fitted_values: List[float]
    r_squared: float
    adjusted_r_squared: float
    residual_std: float  # RMSE: sqrt(SSE / (n - p))
    n_observations: int
    n_parameters: int
    feature_names: List[str] = field(default_factory=list)


def _design_and_names(
    n: int, X: Sequence[Sequence[float]], fit_intercept: bool, feature_names: Optional[Sequence[str]]
):
    """Validate shapes and build the design columns + feature-name list."""
    if n == 0:
        raise ValueError("cannot fit on an empty response series")
    for c in X:
        if len(c) != n:
            raise ValueError("every feature column must match the response length")
    names: List[str] = []
    cols: List[List[float]] = []
    if fit_intercept:
        names.append("intercept")
        cols.append([1.0] * n)
    if feature_names is not None:
        if len(feature_names) != len(X):
            raise ValueError("feature_names must match the number of feature columns")
        names.extend(feature_names)
    else:
        names.extend(f"x{i}" for i in range(len(X)))
    cols.extend(list(c) for c in X)
    return cols, names


def _fit(y: Sequence[float], cols: Sequence[Sequence[float]], names: Sequence[str]) -> RegressionResult:
    n = len(y)
    p = len(cols)
    if n <= p:
        raise ValueError(
            f"need more observations ({n}) than parameters ({p}) to fit with inference"
        )
    # XᵀX and Xᵀy
    xtx = [[sum(cols[c1][r] * cols[c2][r] for r in range(n)) for c2 in range(p)]
           for c1 in range(p)]
    xty = [sum(cols[c][r] * y[r] for r in range(n)) for c in range(p)]

    beta = _solve(xtx, xty)
    fitted = [sum(cols[c][r] * beta[c] for c in range(p)) for r in range(n)]
    residuals = [y[r] - fitted[r] for r in range(n)]

    sse = sum(r * r for r in residuals)
    mean_y = statistics.fmean(y)
    sst = sum((v - mean_y) ** 2 for v in y)
    if sst == 0.0:
        raise ValueError("R² is undefined when the response is constant")
    r_squared = 1.0 - sse / sst

    dof = n - p
    mse = sse / dof
    residual_std = math.sqrt(mse)

    inv = _invert(xtx)
    standard_errors = [math.sqrt(max(mse * inv[c][c], 0.0)) for c in range(p)]
    t_statistics = [(beta[c] / standard_errors[c]) if standard_errors[c] > 0.0 else None
                    for c in range(p)]
    adjusted = 1.0 - (1.0 - r_squared) * (n - 1) / dof

    return RegressionResult(
        coefficients=beta,
        standard_errors=standard_errors,
        t_statistics=t_statistics,
        residuals=residuals,
        fitted_values=fitted,
        r_squared=r_squared,
        adjusted_r_squared=adjusted,
        residual_std=residual_std,
        n_observations=n,
        n_parameters=p,
        feature_names=list(names),
    )


def ols(
    y: Sequence[float],
    X: Sequence[Sequence[float]],
    fit_intercept: bool = True,
    feature_names: Optional[Sequence[str]] = None,
) -> RegressionResult:
    """Ordinary least squares with intercept and full inference.

    ``y`` is the response; ``X`` is a list of feature columns. Returns
    coefficients (intercept first), standard errors, t-statistics, residuals,
    fitted values, R² / adjusted R², and residual stddev.
    """
    cols, names = _design_and_names(len(y), X, fit_intercept, feature_names)
    return _fit(y, cols, names)


def ridge(
    y: Sequence[float],
    X: Sequence[Sequence[float]],
    lam: float = 1.0,
    fit_intercept: bool = True,
    feature_names: Optional[Sequence[str]] = None,
) -> RegressionResult:
    """Ridge (L2-penalized) least squares: ``min ‖y − Xβ‖² + λ‖β‖²``.

    The intercept (when fitted) is NOT penalized. Features are penalized on
    their raw scale, so standardize them (e.g. ``cross_sectional_zscore`` or a
    manual z-score) for scale-invariant regularization.

    Standard errors and t-statistics are returned empty: ridge coefficients are
    biased by design, so OLS-style inference does not apply.
    """
    if lam < 0:
        raise ValueError("ridge penalty must be non-negative")
    cols, names = _design_and_names(len(y), X, fit_intercept, feature_names)
    n = len(y)
    p = len(cols)
    if n <= p:
        raise ValueError(
            f"need more observations ({n}) than parameters ({p}) to fit with inference"
        )
    xtx = [[sum(cols[c1][r] * cols[c2][r] for r in range(n)) for c2 in range(p)]
           for c1 in range(p)]
    xty = [sum(cols[c][r] * y[r] for r in range(n)) for c in range(p)]

    # Add λ to the diagonal of non-intercept columns.
    reg = [list(row) for row in xtx]
    for c in range(p):
        if not (fit_intercept and c == 0):
            reg[c][c] += lam

    beta = _solve(reg, xty)
    fitted = [sum(cols[c][r] * beta[c] for c in range(p)) for r in range(n)]
    residuals = [y[r] - fitted[r] for r in range(n)]

    sse = sum(r * r for r in residuals)
    mean_y = statistics.fmean(y)
    sst = sum((v - mean_y) ** 2 for v in y)
    if sst == 0.0:
        raise ValueError("R² is undefined when the response is constant")
    r_squared = 1.0 - sse / sst
    adjusted = 1.0 - (1.0 - r_squared) * (n - 1) / (n - p)

    return RegressionResult(
        coefficients=beta,
        standard_errors=[],
        t_statistics=[],
        residuals=residuals,
        fitted_values=fitted,
        r_squared=r_squared,
        adjusted_r_squared=adjusted,
        residual_std=math.sqrt(sse / (n - p)),
        n_observations=n,
        n_parameters=p,
        feature_names=list(names),
    )
