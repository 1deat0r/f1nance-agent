# F1NANCE Derivatives Engine

The Phase-8 counterpart to the data, portfolio, quant, execution, desk, and
fixed-income layers. Where the fixed-income engine guarantees a bond or curve
number is never *arithmetically* fabricated, this package guarantees an option
number is never *model-fabricated*: closed-form Black-Scholes pricing, an
honest implied-volatility solver that refuses prices outside the no-arbitrage
bounds, and a lattice that prices the early-exercise premium instead of
hand-waving it.

Hermes-independent by design: standard library only (`math`, `dataclasses`) —
no numpy, no pandas, no scipy, no Hermes. Runs on any Python 3.9+.

## Modules

| Module | What it does |
|---|---|
| `black_scholes` | European pricing (Black-Scholes), closed-form Greeks (delta/gamma/vega/theta/rho), and implied-volatility (bisection) |
| `binomial` | Cox-Ross-Rubinstein lattice for European and American options (early exercise) |

## Use

As a library:

```python
from f1nance.derivatives import black_scholes, greeks, implied_volatility, binomial_price

# price a 1y 100-strike call at 100 spot, 5% rate, 20% vol
p = black_scholes("call", 100, 100, 1, 0.05, 0.20)   # ~10.45

# the risk that travels with it
g = greeks("call", 100, 100, 1, 0.05, 0.20)
print(g.delta, g.gamma, g.vega, g.theta, g.rho)

# solve the vol implied by a market price
iv = implied_volatility(10.45, "call", 100, 100, 1, 0.05)  # ~0.20

# price an American put on a lattice
am = binomial_price("put", 42, 40, 0.5, 0.10, 0.20, steps=500, american=True)
```

From the CLI (all JSON on stdout):

```bash
f1nance/.venv/bin/python -m f1nance.derivatives price spec.json
f1nance/.venv/bin/python -m f1nance.derivatives greeks spec.json
f1nance/.venv/bin/python -m f1nance.derivatives implied_vol spec.json
f1nance/.venv/bin/python -m f1nance.derivatives binomial spec.json
```

## Conventions (trust the number, not the assumption)

- `S`/`K`/price share a currency; `T` is **years**.
- `r` (risk-free), `q` (dividend yield), and `sigma` (vol) are **annualized
  decimal** (`0.05` = 5%), under **continuous compounding** — the same
  convention as `f1nance.fixed_income` with `compounding="continuous"`.
- `call_put` is `"call"` or `"put"` (case-insensitive).
- Greeks are **closed-form**, no finite difference. `theta` is **per year**.
- `implied_volatility` bisects on `[1e-6, 5.0]` and **raises** when the market
  price lies outside the model's no-arbitrage bounds (below intrinsic or above
  the deep-in-the-money limit).
- Degenerate input **raises**: non-positive spot/strike/time/volatility,
  `steps < 1`, a risk-neutral probability outside `[0, 1]`.

## What it deliberately does not do

- No **stochastic volatility / jumps / smile** — Black-Scholes assumes flat,
  constant vol. A market price with a smile still has an implied vol; the
  *smile itself* is a different (surface-modeling) job.
- No **exotics** (barriers, lookbacks, Asian) beyond what a CRR lattice can
  express — the lattice is the honest tool for those, priced by the caller.
- No **market data** — feed it spot, rate, and vol from `f1nance.data` (and
  the `market-data` skill); the rate can come from `f1nance.fixed_income`'s
  discount curve.
- No **Greeks via bumping** — closed-form only, so there is no bump-size
  choice to hide behind.

## Test

```bash
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests -v
```

Offline; no network, no Hermes.
