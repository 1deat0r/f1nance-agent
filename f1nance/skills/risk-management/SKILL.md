---
name: risk-management
description: "Risk limits, stress tests, and VaR backtesting."
version: 0.1.0
author: F1NANCE Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, risk, var, stress-testing, limits, backtesting]
    category: finance
    related_skills: [f1nance, portfolio-management, quant-methods, derivatives, fixed-income]
---

# Risk Management

The risk lens: make "risk first" a checkable contract, not a slogan. A risk
view is three questions answered with numbers — *what are we allowed to hold*
(limits), *what happens if the world moves against us* (stress), and *was our
risk forecast actually right* (VaR backtesting). Answer all three against the
same positions and the same data, and refuse to report a "pass" you did not
compute.

## The engine (`f1nance/risk_management/`)

The discipline below is implemented, stdlib-only, in the Phase-9 native core
(see `f1nance/risk_management/README.md`). Prefer it over hand-rolling:

```python
from f1nance.risk_management import (
    Limit, check_limits, Scenario, stress_test, reverse_stress, var_backtest,
)

report = check_limits(
    [Limit("gross", "max_gross_exposure", 1.5),
     Limit("div", "effective_n", 5, direction="min")],
    {"max_gross_exposure": 1.8, "effective_n": 4},
)   # gross breached, div breached

outcomes = stress_test(
    {"equity": 3_000_000, "rates": 1_000_000},
    [Scenario("crash", {"equity": -0.30})], nav=5_000_000,
)   # P&L -900k, -18% of NAV

rs = reverse_stress({"equity": 3_000_000}, "equity", 600_000)  # shock -0.20

bt = var_backtest([0.05]*100, [...returns...], confidence=0.95)  # Kupiec + Christoffersen
```

CLI (JSON out): `python -m f1nance.risk_management limits|stress|reverse_stress|var_backtest spec.json`.
The engine refuses to fabricate: a limit that references a metric you did not
supply raises, a scenario that shocks nothing raises, a negative VaR forecast
raises.

## When to use

- Setting or checking position/exposure/concentration/risk limits against a
  live book.
- Stress-testing a portfolio under factor shocks (equity crash, rate shock, FX
  move) and reverse-engineering what would break it.
- Validating a VaR model: is the exception rate right, and are exceptions
  random rather than clustered?

Not here: *estimating* VaR (that is `portfolio-management`/`f1nance.portfolio.risk`),
factor-model construction (that is `quant-methods`), or option convexity under a
shock (that is `derivatives` — re-price, don't linearly approximate). This skill
*checks* risk; it does not invent it.

## Limits

- A **max** limit breaches when current exceeds the threshold (exposure, HHI,
  VaR, vol, drawdown). A **min** limit breaches when current is below it
  (diversification, coverage, Sharpe floor).
- **A limit you cannot compute is a limit you have not checked.** If the metric
  is missing, say so and get the number — do not report "ok".
- Report **utilization** (how close to the edge) and **headroom**, not just a
  binary. A book at 95% of every limit is a different risk than one at 40%.

## Stress testing

- Shocks are **return shocks** in decimal form (`-0.30` = -30%); P&L is
  `exposure × shock`, summed over factors. This is **first-order/linear** — it
  does not capture convexity.
- Name the **worst contributor** in every scenario, not just the total.
- **Reverse stress** inverts the question: what shock to one factor produces a
  given loss? That is the number that tells 1deat0r what actually breaks the
  book — lead with it.

## VaR backtesting

- A VaR forecast is a promise: at 95% confidence, losses exceed it ~5% of the
  time. Backtesting checks the promise against realized returns.
- **Kupiec POF** tests the *count* of exceptions. **Christoffersen** tests
  whether exceptions *cluster* — a VaR that breaches in runs is broken even if
  the total count is right. Report both p-values.
- Too many exceptions *and* too few are both miscalibrated: too few means the
  VaR is too conservative (capital wasted), too many means it understates risk.
- An exception is `realized_return < -var_forecast`; keep the sign convention
  straight (VaR is a positive loss, returns are signed).

## Pitfalls

- **Confusing "checked" with "safe".** A green limits report against metrics
  you computed yesterday is not a green book today. Re-check on current data.
- **Linear stress on a convex book.** For options, a -30% equity shock moves
  gamma, not just delta. Re-price with the derivatives engine; don't multiply.
- **Reporting VaR without backtesting it.** A VaR number with no validation is
  a model wearing a costume. If the backtest rejects, say the model is broken —
  don't quietly widen the vol to make it pass.
- **The sign convention.** Mixing positive-loss VaR with signed returns flips
  every exception. State which way your numbers point.

## Delivery

State the limits and their utilization, the scenario P&L with the worst
contributor, and the VaR backtest verdict (rate + clustering p-values). Name
the loss case first: the shock that breaches a limit, how much it costs, and
what the backtest says about whether the risk model can be trusted. Then the
`f1nance` delivery block (thesis + confidence + loss case + data as of).
