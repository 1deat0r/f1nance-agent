---
name: fixed-income
description: "Bond math: pricing, yield curves, duration/convexity."
version: 0.1.0
author: F1NANCE Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, fixed-income, bonds, yield-curve, duration, rates]
    category: finance
    related_skills: [f1nance, market-data, macro-analysis, quant-methods, portfolio-management]
---

# Fixed Income

The fixed-income lens: bonds, yield curves, and the interest-rate risk that
travels with them. A bond is a claim on a stream of cash flows; everything
else — price, yield, duration — is arithmetic on that stream. Get the cash
flows right and refuse to pretend the yield curve is flatter than it is.

## The engine (`f1nance/fixed_income/`)

The discipline below is implemented, stdlib-only, in the Phase-7 native core
(see `f1nance/fixed_income/README.md`). Prefer it over hand-rolling:

```python
from f1nance.fixed_income import (
    bond_price, ytm, duration_and_convexity,
    bootstrap_spot_curve, forward_rate, pv, pv_curve,
)

p = bond_price(0.05, 10, 0.04)                # clean price of a 10y 5% at 4%
y = ytm(108.17, 0.05, 10)                     # solve the implied yield
r = duration_and_convexity(0.05, 10, 0.04)    # modified duration, convexity, DV01
tenors, spots = bootstrap_spot_curve([1, 2, 3], [0.02, 0.025, 0.03])
f = forward_rate(0.02, 0.03, 1, 2)            # implied 1y→2y forward
```

CLI (JSON out): `python -m f1nance.fixed_income price|ytm|duration|pv|pv_curve|forward|bootstrap spec.json`.
The engine refuses to fabricate: it raises on a rate that implies a
non-positive discount factor, on extrapolating outside the curve, and on a
bootstrap that cannot exist — rather than returning a number with no economic
meaning.

## When to use

- Valuing or analyzing bonds, notes, bills, or a portfolio of them.
- Building, interpolating, or interpreting a yield curve (spot/par/forward).
- Measuring interest-rate risk (duration, convexity, DV01) and explaining it.
- Decomposing a yield into expectations + term premium (needs macro-analysis).

Not here: credit spreads and default risk (that is a credit analysis, not a
bond-math question), embedded options (need a lattice), or day-count/settlement
convention work (the engine prices clean and says so).

## Pricing and yield

- **Price vs. yield move inversely.** At par, price = face and yield = coupon.
  Yield below coupon → premium; above → discount. Zero-coupon price is face
  discounted at the yield for the full maturity.
- **Yield-to-maturity is a single flat discount rate** applied to every cash
  flow. It assumes the curve is flat at that rate — a convenience, not a
  description of the term structure. When the curve is steep, price off the
  spot curve (`pv_curve`), not a single YTM.
- **Clean vs. dirty.** The engine prices clean (whole coupon periods).
  Settlement-day accrual and day-count convention (Actual/Actual, 30/360) are
  deliberately left out; add them explicitly if a dirty price is required.

## Duration and convexity

- **Macaulay duration** is the weighted-average time to each cash flow (a
  zero-coupon bond's duration is its maturity). **Modified duration** is the
  percentage price change per unit yield move; **DV01** is the absolute price
  change per 1 bp.
- Duration is a **first-order, parallel-shift** approximation. It is accurate
  only for small, uniform moves. Convexity is the second-order correction —
  positive for plain bonds (price falls less than duration predicts when
  yields rise). Neither captures curve *steepening/flattening*; for that you
  re-price against the full curve.
- Always report duration *and* convexity together, and state the yield at
  which they are measured (they change as the bond rolls down the curve).

## The yield curve

- **Spot, par, and forward rates** are three views of the same curve. Spot
  rates discount a single future cash flow; par yields are the coupons of
  bonds priced at par; forward rates are the future spot rates implied by
  today's curve. Bootstrapping extracts the spot curve from par yields.
- **An inverted curve is a real market state**, not an error — forward rates
  can be negative. Report them; don't "fix" them.
- **Interpolation is a modeling choice.** The engine interpolates linearly on
  spot rates and refuses to extrapolate past the last tenor. A 20-year
  discount factor from a 10-year curve is a guess — say it's a guess.
- Live treasury yields come from the data layer, not the model: FRED
  constant-maturity series (`DGS2`, `DGS5`, `DGS10`, `DGS30`) via
  `market_macro` / the `market-data` skill.

## Pitfalls

- **Treating YTM as a discount curve.** It is one number, not a term
  structure. Use it for quoting, not for valuing a cash-flow stream off a
  steep curve.
- **Duration outside its domain.** A 200 bp parallel shift, or a curve
  steepener, is not a duration question — re-price.
- **Ignoring convexity asymmetry.** Positive convexity is valuable; a
  callable/putable bond's convexity flips sign and duration lies.
- **Negative yields are legal.** Do not floor a negative rate to zero or
  "correct" an inverted curve.
- **Risk-free vs. credit.** Treasury bond math is the risk-free curve; a
  corporate bond's yield embeds a spread you have not priced. Never present a
  treasury-implied price as a corporate price.

## Delivery

State the price/yield, the curve used, its as-of date, and the risk numbers
(duration, convexity, DV01) at the measuring yield. Name the loss case first:
the yield move that hurts, how much duration says it costs, and what breaks
the convexity assumption. Then the `f1nance` delivery block (thesis +
confidence + loss case + data as of).
