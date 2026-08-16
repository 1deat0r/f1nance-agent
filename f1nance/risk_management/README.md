# F1NANCE Risk-Management Engine

The Phase-9 layer that makes "risk first" a checkable contract rather than a
slogan. Where `f1nance.portfolio.risk` (Phase 2) computes the *numbers* (VaR,
CVaR, volatility, drawdown, concentration) and `f1nance.derivatives` (Phase 8)
computes the *sensitivities* (gamma/vega), this package enforces and validates
them: named limits, scenario stress tests, and VaR backtesting.

Hermes-independent by design: standard library only (`math`, `dataclasses`) —
no numpy, no pandas, no scipy, no Hermes. Runs on any Python 3.9+.

## Modules

| Module | What it does |
|---|---|
| `limits` | `Limit` (max/min threshold on a metric), `check_limits` → breach / utilization / headroom |
| `stress` | `Scenario` (factor shocks), `stress_test` (linear P&L per scenario), `reverse_stress` (solve the shock for a target loss) |
| `backtest` | `var_backtest` → Kupiec POF + Christoffersen independence + conditional coverage, each with a p-value |

## Use

As a library:

```python
from f1nance.risk_management import (
    Limit, check_limits, Scenario, stress_test, reverse_stress, var_backtest,
)

# limits
report = check_limits(
    [Limit("gross", "max_gross_exposure", 1.5),
     Limit("div", "effective_n", 5, direction="min")],
    {"max_gross_exposure": 1.8, "effective_n": 4},
)   # gross breached, div breached

# stress
outcomes = stress_test(
    {"equity": 3_000_000, "rates": 1_000_000},
    [Scenario("crash", {"equity": -0.30})],
    nav=5_000_000,
)   # P&L -900k, -18% of NAV

# reverse stress
rs = reverse_stress({"equity": 3_000_000}, "equity", 600_000)  # shock -0.20

# VaR backtest
bt = var_backtest([0.02]*100, [ ...100 realized returns... ], confidence=0.95)
print(bt.kupiec_reject, bt.christoffersen_reject)
```

From the CLI (all JSON on stdout):

```bash
f1nance/.venv/bin/python -m f1nance.risk_management limits spec.json
f1nance/.venv/bin/python -m f1nance.risk_management stress spec.json
f1nance/.venv/bin/python -m f1nance.risk_management reverse_stress spec.json
f1nance/.venv/bin/python -m f1nance.risk_management var_backtest spec.json
```

## Conventions (trust the number, not the assumption)

- Exposures are in portfolio currency; scenario shocks are **decimal returns**
  (``-0.30`` = -30%). Stress P&L is **linear and first-order** — no convexity.
- VaR forecasts are **positive loss numbers**; realized returns are **signed**;
  an exception is ``realized < -var``. This matches `f1nance.portfolio.risk`.
- A limit that references a **missing metric raises** — a fabricated "pass" is
  exactly what this layer exists to prevent.
- p-values come from the chi-square survival function (`df=1` for Kupiec and
  independence, `df=2` for conditional coverage); `*_reject` is `p < significance`.

## What it deliberately does not do

- No **factor-model construction** — feed it exposures from the portfolio and
  quant engines; it only shocks them.
- No **non-linear / convexity stress** — for an options book, re-price under the
  shock with `f1nance.derivatives` rather than trusting a linear approximation.
- No **VaR *estimation*** — it *validates* VaR forecasts made elsewhere
  (`f1nance.portfolio.risk` historical/parametric VaR). It does not make them.
- No **market data** — all inputs are computed upstream.

## Test

```bash
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests -v
```

Offline; no network, no Hermes.
