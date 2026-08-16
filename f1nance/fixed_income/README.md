# F1NANCE Fixed-Income Engine

The Phase-7 counterpart to the data, portfolio, quant, and execution layers.
Where the data layer guarantees a number is never *fetched-fabricated* and the
quant layer guarantees a backtest is never *statistically* fabricated, this
package guarantees a bond or curve number is never *arithmetically* fabricated:
closed-form pricing, an honest YTM solver, and a bootstrap that raises rather
than inventing a discount factor that cannot exist.

Hermes-independent by design: standard library only (`math`, `dataclasses`) —
no numpy, no pandas, no scipy, no Hermes. Runs on any Python 3.9+.

## Modules

| Module | What it does |
|---|---|
| `curves` | discount factors, spot/forward rates, present value (flat + curve), and par→spot bootstrapping |
| `bonds` | clean-price bond pricing, yield-to-maturity (bisection), and Macaulay/modified duration, convexity, DV01 |

## Use

As a library:

```python
from f1nance.fixed_income import bond_price, ytm, duration_and_convexity
from f1nance.fixed_income import bootstrap_spot_curve, forward_rate, pv

# price a 10y 5% bond at a 4% yield (semiannual)
p = bond_price(0.05, 10, 0.04)                 # ~108.18

# solve the yield implied by a price
y = ytm(108.17, 0.05, 10)                      # ~0.04

# interest-rate risk
r = duration_and_convexity(0.05, 10, 0.04)
print(r.modified_duration, r.convexity, r.dv01)

# curve math
tenors, spots = bootstrap_spot_curve([1, 2, 3], [0.02, 0.025, 0.03])
f = forward_rate(0.02, 0.03, 1, 2)             # implied 1y→2y forward
```

From the CLI (all JSON on stdout):

```bash
f1nance/.venv/bin/python -m f1nance.fixed_income price spec.json
f1nance/.venv/bin/python -m f1nance.fixed_income ytm spec.json
f1nance/.venv/bin/python -m f1nance.fixed_income duration spec.json
f1nance/.venv/bin/python -m f1nance.fixed_income pv spec.json
f1nance/.venv/bin/python -m f1nance.fixed_income pv_curve spec.json
f1nance/.venv/bin/python -m f1nance.fixed_income forward spec.json
f1nance/.venv/bin/python -m f1nance.fixed_income bootstrap spec.json
```

## Conventions (trust the number, not the assumption)

- Rates are **annualized decimal** (`0.05` = 5%); times are **years**.
- `compounding` is periods/year (`1`, `2`, `12`, …) or `"continuous"`.
- Prices are **clean** (whole coupon periods); `face` defaults to 100.
- `interpolate_spot` is linear on spot rates and **raises outside the curve
  range** — no silent extrapolation.
- `forward_rate` may be **negative** (an inverted curve is a real market
  state, not an error).
- `bootstrap_spot_curve` assumes annual-coupon par bonds at consecutive
  integer-year tenors (`1..N`).
- Degenerate input **raises**: negative time, a rate that implies a
  non-positive discount factor, non-increasing tenors, non-integer period
  counts, a non-positive price.

## What it deliberately does not do

- No **day-count / accrued-interest conventions** (Actual/Actual, 30/360, …).
  The engine prices clean; settlement, dirty price, and accrual are the
  caller's. Implementing a half of one convention is worse than none.
- No **embedded options** (callable/putable) — those need a lattice, not
  closed-form discounting.
- No **credit spread / default modeling** — this is the risk-free curve and
  bond math; credit is a different engine's job.
- No data sourcing — feed it yields from `f1nance.data` (FRED treasury
  constant-maturity series like `DGS2`/`DGS5`/`DGS10` via `get_macro_series`).

## Test

```bash
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests -v
```

Offline; no network, no Hermes.
