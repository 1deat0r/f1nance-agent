# F1NANCE Portfolio & Risk Engine

The Phase-2 counterpart to the `f1nance/data` substrate. Where the data layer
guarantees a number is never *fetched-fabricated* (source + as-of + degraded on
every result), this package guarantees a number is never *arithmetically*
fabricated: every market value, weight, exposure, risk metric, and attribution
term is computed from explicit inputs, and a missing FX rate or a degenerate
input raises instead of guessing.

Hermes-independent by design: standard library only (`dataclasses`, `math`,
`statistics`) — no numpy, no pandas, no Hermes. Runs on any Python 3.9+.

## Modules

| Module | What it does |
|---|---|
| `positions` | `Position` / `Portfolio`: weights, exposure (long/short/gross/net), FX, cash drag, rebalance trades |
| `risk` | returns, volatility, Sharpe/Sortino, VaR/CVaR, beta/correlation, drawdown, concentration |
| `attribution` | Brinson-Fachler allocation / selection / interaction |

## Use

As a library:

```python
from f1nance.portfolio import Portfolio, Position, brinson
from f1nance.portfolio.risk import annualized_volatility, var_historical, max_drawdown, beta

p = Portfolio(
    positions=[
        Position("AAPL", 100, 210.0),
        Position("SAP", 50, 100.0, currency="EUR"),
    ],
    cash={"USD": 5000},
    fx_rates={"EUR": 1.09},
)
print(p.market_value())          # 31450.0
print(p.weights())               # {'AAPL': 0.668, 'SAP': 0.173, 'CASH': 0.159}
print(p.exposure())              # Exposure(long=0.841, short=0.0, gross=0.841, net=0.841)

r = brinson({"A": 0.7, "B": 0.3}, {"A": 0.6, "B": 0.4},
            {"A": 0.12, "B": 0.03}, {"A": 0.10, "B": 0.05})
print(r.active_return)           # 0.013 (allocation + selection + interaction)
```

From the CLI (all JSON on stdout):

```bash
f1nance/.venv/bin/python -m f1nance.portfolio value spec.json
f1nance/.venv/bin/python -m f1nance.portfolio risk prices.json
f1nance/.venv/bin/python -m f1nance.portfolio attr spec.json
```

## Conventions (trust the number, not the assumption)

- **Weights** are fractions of total NAV *including* cash; cash is the residual.
- **Exposure** is quoted as a multiple of NAV; long-only fully invested = 1.0.
- **Drawdown** is a positive magnitude (`0.20` = 20% peak-to-trough).
- **VaR/CVaR** are positive loss numbers.
- **Stddev** is population (ddof=0), matching numpy's default.
- Degenerate inputs (empty returns, zero variance, mismatched series, missing
  FX rate, target weights that don't sum to 1.0) **raise** rather than return
  a misleading 0 or inf.

## Test

```bash
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests -v
```

Offline; no network, no Hermes.
