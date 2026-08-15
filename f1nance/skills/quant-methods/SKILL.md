---
name: quant-methods
description: "Quant discipline: return statistics, factor models, regression, time series, and honest backtesting (no look-ahead, walk-forward, costs)."
version: 0.2.0
author: F1NANCE Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, quantitative, backtesting, factors, statistics, machine-learning, risk]
    category: finance
    related_skills: [f1nance, market-data, portfolio-management]
---

# Quantitative Methods

The quant lens: build models that are *actually* predictive, not just
retrospectively fitted. The discipline is the product; the model is a
byproduct.

## The engine (`f1nance/quant/`)

The discipline below is implemented, stdlib-only, in the Phase-3 native core
(see `f1nance/quant/README.md`). Prefer it over hand-rolling:

```python
from f1nance.quant import capm, multi_factor, momentum_predictor, walk_forward
m = capm(asset_returns, market_returns)          # alpha, beta, R², residual vol
m = multi_factor(asset_returns, {"MKT": ..., "SMB": ...})  # factor exposures
r = walk_forward(history, momentum_predictor(lookback=5, top_k=1),
                 min_train=10, cost_bps=2.0, slippage_bps=1.0)
r.out_of_sample        # the honest number
r.in_sample.lookahead  # True — the leaky baseline, reported only for contrast
```

CLI (JSON out): `python -m f1nance.quant capm|ff|backtest|momentum spec.json`.
The harness enforces the non-negotiables so you can't skip them by accident:
point-in-time data only (the predictor never sees the future), costs charged on
turnover, in-sample flagged `lookahead=True`, and degenerate input raises
rather than fabricating.

## Return statistics first

- Use **log returns** for time-series math, **simple returns** for
  cross-sectional/portfolio aggregation.
- Skewness and kurtosis: markets are fat-tailed and negatively skewed. The
  Gaussian is a convenience, not a fact.
- **Stationarity:** price series are not stationary; returns (mostly) are.
  Test (ADF) before regressing — a non-stationary regression is spurious.

## Factor models

- **Single-factor (CAPM):** `R_i − R_f = α + β(R_m − R_f) + ε`. Alpha is the
  intercept — and the thing you claim is skill.
- **Multi-factor (Fama-French / Carhart):** add SMB (size), HML (value), UMD
  (momentum). A strategy that "beats the market" but has high SMB/HML loading
  is not alpha, it is factor exposure — and it is replicable cheaply.
- **Barra-style risk factors:** vol, size, value, momentum, quality, growth.
- Always report **exposures** (betas) and **residual risk** alongside alpha.

## Regression & model pitfalls

- **Overfitting** is the default outcome, not the exception. More features +
  less data = a memorized past. Regularize (ridge/lasso), cross-validate, and
  penalize complexity.
- **Look-ahead bias:** using information not available at decision time
  (today's index membership, restated fundamentals, full-sample means). This
  is the single most common way a backtest lies.
- **Survivorship bias:** backtesting only on companies that still exist.
- **Multiple-testing:** with enough trials, something will look significant by
  chance. Deflate expectations (Bonferroni/Holm) or demand economic
  plausibility, not just p < 0.05.

## Backtesting discipline (non-negotiable)

1. **Point-in-time data** only — the universe and fundamentals as they were on
   each date, not as restated later.
2. **Walk-forward / out-of-sample:** fit on a training window, test on data
   the model never saw. Rolling-window or expanding-window, but always a
   genuine holdout.
3. **Transaction costs and slippage** modeled explicitly (bps per side, plus
   market-impact on size). A strategy that nets +50bp/year gross is a
   *loser* after 20bp of costs.
4. **Capacity and liquidity** — a great backtest in micro-caps does not
   survive real size.
5. **Report** Sharpe, max drawdown, turnover, and the equity curve — never
   just the CAGR. A high return with a −60% drawdown is not investable.
6. **Economic story required.** If you can't explain *why* it should keep
   working, treat it as curve-fitting until proven otherwise.

## What "validated" means here

A model is validated when: (a) the signal is economically motivated, (b) it
survives out-of-sample, (c) it survives costs, (d) it is stable across
sub-periods, and (e) you can name the regime that would kill it. Anything
less is a candidate, not a conclusion.

## Delivery

State the model, its assumptions, its exposures, and its honest out-of-sample
metrics. Lead with the loss case and the regime that breaks it (see the
`f1nance` delivery block). A quant deliverable that hides its drawdown or its
look-ahead bias is fraud against its own principal.

## Pitfalls

- **Reusing the same data to discover and confirm** a signal (data snooping).
- **Annualizing Sharpe by √252** on daily data with autocorrelation — the
  multiplier overstates.
- **Ignoring the risk-free rate / financing cost** in leveraged backtests.
- **P-hacking via parameter grids** then reporting the best cell.
- **Confusing correlation with a tradeable edge** — co-movement is not
  necessarily excess return.
