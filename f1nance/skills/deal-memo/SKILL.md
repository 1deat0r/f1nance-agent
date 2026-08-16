---
name: deal-memo
description: "Score a deal: accretion, synergies, LBO, risk, one verdict."
version: 0.1.0
author: F1NANCE Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, investment-banking, m-and-a, risk, deal-memo, accretion, lbo, stress-test]
    category: finance
    related_skills: [f1nance, valuation, m-and-a, risk-management, financial-statement-analysis]
---

# Deal Memo

The integration lens: one verdict over the whole deal. Where `m-and-a` answers
each deal-mechanics question on its own and `risk-management` answers the risk
question, the deal memo chains them — **valuation inputs → M&A → risk → one
scored recommendation** — and *derives* that recommendation from the numbers.
It never asserts an opinion it did not compute: a section it could not compute
is reported as `not_computed` with the reason, not a fabricated pass.

## The engine (`f1nance/deal_memo/`)

The discipline below is implemented, stdlib-only, in the Phase-11 native core
(see `f1nance/deal_memo/README.md`). Prefer it over hand-rolling:

```python
from f1nance.deal_memo import build_deal_memo

memo = build_deal_memo({
    "deal_id": "acme-buys-beta",
    "merger": {"acquirer_ni": 500, "acquirer_shares": 100, "target_ni": 120,
               "purchase_price": 2000, "cash_portion": 1000, "stock_portion": 1000,
               "acquirer_share_price": 50, "tax_rate": 0.25,
               "cost_synergies": 100, "new_debt_rate": 0.05,
               "discount_rate": 0.10, "ramp_years": 2,
               "premium_paid": 400, "integration_costs": 50},
    "risk": {"nav": 30520,
             "metrics": {"gross_exposure": 1.20},
             "limits": [{"name": "gross exposure", "metric": "gross_exposure",
                         "threshold": 1.50}],
             "exposures": {"equity": 20000.0},
             "scenarios": [{"name": "equity -30%", "shocks": {"equity": -0.30}}],
             "loss_budget": 5000},
})
print(memo.recommendation)   # "adverse" — the stress loss breaches the budget
```

CLI (JSON out): `python -m f1nance.deal_memo memo spec.json`.
Agent tool: `dealmemo_run` takes the same `spec` object.

## When to use

- When 1deat0r wants a single, numbers-backed read on a whole deal — merger,
  LBO, or both — instead of three separate engine outputs.
- As the **first pass** on any deal: run the memo, then drill into whichever
  check failed or skipped with the underlying `m-and-a` / `risk-management`
  tools.
- When the "risk first" guardrail needs to be *on the same page as the return*:
  the memo names the headline stress loss before the accretion upside.

Not here: *standalone valuation* (that is `valuation`), *reading the three
statements* (that is `financial-statement-analysis`), or *building a position*
(that is `execution-trading`). The memo scores a deal on top of a value; it
does not value the target.

## The scorecard

The recommendation is a pure function of the checks — no discretion:

- **accretion** — `pass` if the deal is accretive, `fail` if dilutive.
- **synergy coverage** — `pass` if net synergy value covers the premium plus
  integration costs, `fail` otherwise.
- **sponsor return** — `pass` if LBO IRR meets `hurdle_irr`, `fail` if below,
  `skip` if no hurdle was supplied (a return is meaningless without a target).
- **risk limits** — `pass` if no limit is breached, `fail` if any is (named).
- **stress budget** — `pass` if the worst scenario P&L is within `loss_budget`,
  `fail` if it exceeds it, `skip` if no budget was supplied.

The verdict:

- any `fail` → **adverse** (failing checks and loss cases named);
- no fail but a `skip`, or nothing computable → **inconclusive** (evidence
  missing — do not recommend);
- otherwise → **favorable**.

## Procedure

1. Gather the inputs (valuation first — a bad price accretes a bad deal).
2. Build the spec: a `merger` block (and/or `lbo`) plus a `risk` block.
   Supply a `hurdle_irr` for an LBO and a `loss_budget` for the stress gate —
   without them those checks report but cannot gate.
3. Run `build_deal_memo` (or the `dealmemo_run` tool). Read `not_computed`
   first: anything there is a number you still need, not a number you have.
4. Report the scorecard verbatim, then the recommendation, then the loss cases
   (headline stress loss first), then the falsification condition.

## Pitfalls

- **Missing is not passing.** A `skip` or a `not_computed` section is evidence
  you do not have — do not upgrade it to a pass because the other checks look
  good.
- **`hurdle_irr` and `loss_budget` are the gates.** Leave them out and the memo
  degrades to `inconclusive` on exactly the checks that matter — the return
  target and the loss tolerance.
- **One synergy number, one deal.** The same `cost_synergies` feeds accretion
  and synergy value; do not put $80 into one and $100 into the other.
- **Stress is linear.** The scenario P&L is `Σ exposure × shock`, first-order.
  For an options book, re-price through the `derivatives` engine rather than
  trusting the linear approximation.

## Delivery

State the recommendation, then the scorecard (each check with its number), then
the loss cases (headline stress loss first), then the falsification condition.
Then the `f1nance` delivery block (thesis + confidence + loss case + data as of).
