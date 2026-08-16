---
name: derivatives
description: "Options pricing, Greeks, and implied volatility."
version: 0.1.0
author: F1NANCE Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, derivatives, options, black-scholes, greeks, volatility]
    category: finance
    related_skills: [f1nance, market-data, quant-methods, fixed-income, risk-management, portfolio-management]
---

# Derivatives

The derivatives lens: options and the volatility risk that travels with them.
An option is a claim on the *distribution* of a future price, not the price
itself — everything else (value, delta, gamma, vega, the implied vol) is
arithmetic on that distribution. Get the payoff and the discounting right,
and refuse to pretend volatility is constant when the market is telling you
it is not.

## The engine (`f1nance/derivatives/`)

The discipline below is implemented, stdlib-only, in the Phase-8 native core
(see `f1nance/derivatives/README.md`). Prefer it over hand-rolling:

```python
from f1nance.derivatives import (
    black_scholes, greeks, implied_volatility, binomial_price,
)

p = black_scholes("call", 100, 100, 1, 0.05, 0.20)   # European value
g = greeks("call", 100, 100, 1, 0.05, 0.20)          # delta/gamma/vega/theta/rho
iv = implied_volatility(10.45, "call", 100, 100, 1, 0.05)  # ~0.20
am = binomial_price("put", 42, 40, 0.5, 0.10, 0.20, steps=500, american=True)
```

CLI (JSON out): `python -m f1nance.derivatives price|greeks|implied_vol|binomial spec.json`.
Conventions match the fixed-income engine: rates and vol are **annualized
decimal** under **continuous compounding**; time is **years**. The engine
refuses to fabricate: it raises on non-positive spot/strike/time/vol, and the
implied-vol solver raises on a price outside the model's no-arbitrage bounds.

## When to use

- Valuing plain-vanilla calls and puts, or a portfolio of them.
- Measuring and explaining option risk (delta, gamma, vega, theta, rho).
- Reading a market price back into an implied volatility, or a vol surface.
- Pricing an American-style option (early exercise) or a payoff Black-Scholes
  cannot price closed-form, via the binomial lattice.

Not here: exotic payoffs (barriers, lookbacks, Asians) beyond what a lattice
expresses, stochastic-vol/jump models, or the vol *smile* itself — those are
surface-modeling and calibration jobs, not one-option arithmetic. Credit and
counterparty risk on a derivative is a credit analysis, not an option-math
question.

## Pricing and parity

- **Black-Scholes is one model, not the truth.** It assumes log-normal spot,
  constant vol, no jumps, continuous hedging. Quote it as a benchmark, not as
  the price the market must meet. When the market disagrees, the disagreement
  *is* the information (it is the vol smile).
- **Put-call parity is a law, not a model.** `C - P = S e^{-qT} - K e^{-rT}`.
  A pair that breaks parity is an arbitrage — flag it, never quote both sides
  from inconsistent inputs.
- **Intrinsic vs. time value.** Below intrinsic is arbitrage; the time value
  is the cost of optionality and decays (theta). A market price with no real
  implied vol is a data error or an arbitrage — say so, don't force a vol.
- **American ≠ European.** Early exercise has value for puts (and calls with
  dividends). Price those on the lattice, not the closed form.

## The Greeks

- **Delta** is the first-order exposure to spot; **gamma** is how fast delta
  moves; **vega** is the exposure to volatility (the big one — options are
  mostly a vol trade); **theta** is time decay (per year in the engine);
  **rho** is the rate exposure.
- Greeks are **closed-form** here, not bump-and-reprice — there is no bump
  size to hide behind. But they are still *local*: a 20% vol move, a jump, or
  a regime change is not a Greeks question — re-price.
- Gamma and vega are symmetric (same for calls and puts); delta and rho flip
  sign. The engine's tests assert those invariants, and so should your
  reasoning.

## The volatility surface

- **Implied vol is the number that makes the model fit the market price.** It
  is a quote, not a forecast. The smile/skew (higher IV for OTM puts) means
  the market does not believe Black-Scholes — that belief is priced in.
- **Historical vol is a backward-looking input, not a forward-looking price.**
  Never present realized vol as the implied vol. Label which one you mean.
- Inputs come from the data layer, not the model: spot from `market_price`,
  the risk-free rate from the `fixed-income` curve (a discount factor is a
  risk-free rate), historical vol from realized returns via the `quant`
  engine. Do not invent a vol.

## Pitfalls

- **Treating Black-Scholes as reality.** It is a translation device. The
  output is only as good as the vol you feed it.
- **Quoting delta without gamma.** Delta alone hides the convexity; a
  short-gamma position behaves very differently from its delta suggests.
- **Forcing an implied vol on an arbitrage price.** A price below intrinsic
  or above the no-arbitrage bound has no real vol — the engine raises; so
  should you.
- **Ignoring early exercise.** Pricing an American put with the European
  closed form understates its value. Use the lattice.
- **Conflating historical and implied vol.** They measure different things.
  A view that leans on the difference between them must say which is which.
- **Hedging with a model you don't believe.** A Black-Scholes hedge is only
  a hedge if the model's assumptions hold. Name the residual (jump, smile,
  gap) risk explicitly.

## Delivery

State the price, the model and its vol input, the as-of date, and the Greeks
at that vol. Name the loss case first: the vol move or spot gap that hurts,
how much gamma/vega says it costs, and what breaks the constant-vol
assumption. Then the `f1nance` delivery block (thesis + confidence + loss
case + data as of).
