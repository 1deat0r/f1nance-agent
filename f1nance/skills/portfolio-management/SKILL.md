---
name: portfolio-management
description: "Build and manage a portfolio: allocation, risk metrics (vol, Sharpe, drawdown, VaR), rebalancing, attribution, position sizing."
version: 0.2.0
author: F1NANCE Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, portfolio, asset-allocation, risk, sharpe, rebalancing, attribution]
    category: finance
    related_skills: [f1nance, market-data, quant-methods, valuation]
---

# Portfolio Management

The hedge-fund / portfolio-manager / advisor lens: turn a set of ideas into a
portfolio that survives, and measure how well it actually did.

## The engine (`f1nance/portfolio`)

The arithmetic below is implemented in the stdlib-only `f1nance/portfolio`
package — use it rather than hand-rolling the math, so a number is never
arithmetically fabricated and every degenerate input raises instead of guessing.
See `f1nance/portfolio/README.md` for full API.

```python
from f1nance.portfolio import Portfolio, Position, brinson
from f1nance.portfolio.risk import (annualized_volatility, sharpe_ratio,
                                    var_historical, cvar_historical,
                                    max_drawdown, beta, concentration)

p = Portfolio(positions=[Position("AAPL", 100, 210.0)],
              cash={"USD": 5000}, fx_rates={"EUR": 1.09})
p.market_value(); p.weights(); p.exposure(); p.cash_drag(0.08)
```

CLI: `f1nance/.venv/bin/python -m f1nance.portfolio value|risk|attr <spec.json>`.

## Start from the investor, not the assets

- **Objectives** (return target, income vs. growth), **horizon**, **liquidity
  needs**, and **risk capacity** (ability to bear loss) vs. **risk tolerance**
  (willingness). These two are different and both matter.
- Document an **Investment Policy Statement** (IPS): objectives, constraints,
  eligible instruments, risk limits, rebalancing rules. Everything after this
  is checked against it.

## Allocation (top-down → bottom-up)

1. **Strategic asset allocation** sets the long-run mix (equities / fixed
   income / cash / alts) from the IPS.
2. **Tactical tilts** adjust around it within bands (e.g. ±5%), always with a
   thesis and a date.
3. Mean-variance optimization (MVO) is a starting point, not a prescription:
   it is extremely sensitive to expected-return estimates. Prefer robust
   variants (e.g. inverse-vol, risk parity, or a blended heuristic) when
   return forecasts are noisy — which they always are.

## Risk metrics (compute on daily returns, annualize)

```
Return R = (P_t/P_{t-1}) − 1, annualized ≈ mean(R)·252
Vol (σ)  = std(R)·√252
Sharpe   = (R_p − R_f) / σ_p           # annualized; R_f = short-term risk-free
Sortino  = (R_p − R_f) / downside_σ    # only below target
Max drawdown = max over t of (1 − P_t / running_max)
Beta     = cov(R_p, R_m) / var(R_m)
Corr     = corr(R_p, R_m)
VaR(95%) ≈ 1.645·σ  (parametric, daily), scale by √h for horizon
CVaR     = mean of losses beyond VaR
```

- Report **geometric** (compound) returns for actual money; arithmetic for
  expected-value math. The difference is the variance drag (~σ²/2).
- Vol is not risk; **drawdown** and **CVaR** are closer to what an investor
  feels. Present both.

## Position sizing

- **Vol targeting:** weight ∝ 1/σ so each position contributes equal risk.
- **Equal weight** as a naive benchmark — hard to beat without real edge.
- **Kelly** (f* = (bp − q)/b for binary, or f* = μ/σ² for continuous) is an
  *upper bound*, not a target: use a fraction (¼–½ Kelly) or it will ruin you
  on estimation error.
- **Concentration caps:** single name and sector limits from the IPS.
- **Cash drag** is real: uninvested cash is a position too.

## Rebalancing

- **Calendar** (e.g. quarterly) vs. **band** (when a weight drifts past ±X%).
- Rebalancing is a volatility seller: it buys what fell and trims what ran —
  it adds to returns in choppy markets and costs in trends. Do it on a rule,
  not on feeling.
- Mind taxes and transaction costs: rebalance fewer, larger positions or use
  cash flows (new contributions) to nudge weights instead of trading.

## Performance attribution

- **Allocation vs. selection:** how much of active return came from being
  overweight/underweight a sector vs. picking winners within it.
- **Brinson model:** `R_active = Σ (w_p − w_b)·R_b + Σ w_p·(R_p − R_b)`.
- Separate **skill from beta**: regress returns on a market/factor index; the
  alpha is the intercept. If alpha is statistically indistinguishable from
  zero, the "skill" is exposure.

## Pitfalls

- **Backtest ≠ live.** Survivorship, look-ahead, and no transaction costs
  flatter every backtest. See `quant-methods` for the validation discipline.
- **Chasing the last drawdown.** Reallocating based on recent losses
  crystallizes them. Stick to the IPS unless the thesis changed.
- **Leverage compounds both ways.** State gross and net exposure explicitly.
- **Reporting only since inception.** Start dates flatter; report since a
  peak or over full cycles too.
- **Illiquidity priced as free.** A position you can't exit is riskier than
  its vol suggests.
