# F1NANCE Quant & Backtesting Engine

The Phase-3 counterpart to the `f1nance/data` and `f1nance/portfolio` layers.
Where the data layer guarantees a number is never *fetched-fabricated* and the
portfolio layer guarantees a number is never *arithmetically* fabricated, this
package guarantees a backtest is never *statistically* fabricated: point-in-time
signals only, explicit costs, and a hard separation of in-sample (look-ahead)
from out-of-sample results.

Hermes-independent by design: standard library only (`math`, `statistics`,
`dataclasses`) — no numpy, no pandas, no scipy, no Hermes. Runs on any Python
3.9+.

## Modules

| Module | What it does |
|---|---|
| `linear` | OLS + ridge regression with full inference (coefficients, std errors, t-stats, R²) over a minimal stdlib linear algebra core |
| `factors` | CAPM and multi-factor exposure models, cross-sectional z-score / rank, trailing-return momentum and a point-in-time momentum predictor |
| `backtest` | walk-forward backtesting harness: rolling/expanding origin, transaction costs + slippage, look-ahead guards, honest IS/OOS reporting |

## Use

As a library:

```python
from f1nance.quant import capm, multi_factor, momentum_predictor, walk_forward

# exposure: how much "skill" survives factor accounting
m = capm([0.02, -0.01, 0.03, 0.01], [0.01, 0.00, 0.02, 0.01])
print(m.alpha, m.exposures)          # intercept + {'market': beta}

# a real walk-forward momentum backtest (point-in-time, costs included)
history = {"A": [...], "B": [...], "C": [...]}   # aligned period returns
result = walk_forward(
    history,
    momentum_predictor(lookback=5, top_k=1),
    min_train=10,
    cost_bps=2.0, slippage_bps=1.0,
)
print(result.out_of_sample.total_return)   # the honest number
print(result.in_sample.lookahead)          # True — this one is the leaky baseline
```

From the CLI (all JSON on stdout):

```bash
f1nance/.venv/bin/python -m f1nance.quant capm spec.json
f1nance/.venv/bin/python -m f1nance.quant ff spec.json
f1nance/.venv/bin/python -m f1nance.quant backtest spec.json
f1nance/.venv/bin/python -m f1nance.quant momentum spec.json
```

## Conventions (trust the number, not the assumption)

- Returns are **period returns** in decimal form (`0.01` = +1%).
- **Annualized alpha** is arithmetic (`alpha × periods_per_year`).
- **Turnover** is `Σ |Δweight|` per period; the initial deployment counts as
  turnover 1.0 and is charged costs (you pay to build the book).
- **Costs** (bps) are subtracted net of gross return every period.
- **Drawdown** is a positive magnitude (`0.20` = 20% peak-to-trough).
- **In-sample is always flagged** `lookahead=True` and reported only for
  contrast with the honest out-of-sample record.
- Degenerate input **raises**: mismatched series, weights that don't sum to
  1.0, a held asset with no return, a collinear design matrix, a cross-section
  with zero variance, or a `min_train` that leaves no holdout.

## What it deliberately does not do

- No p-values (that needs a Student-t CDF / scipy); t-statistics and standard
  errors are reported so significance is assessable without a false-precision
  number. The discipline prefers an economic story to `p < 0.05` anyway.
- No Lasso (L1 path solver is scipy territory); ridge is provided for
  regularization.
- No data sourcing — feed it series from `f1nance.data`, whose as-of /
  source / degraded provenance is the honest input a backtest deserves.

## Test

```bash
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests -v
```

Offline; no network, no Hermes.
