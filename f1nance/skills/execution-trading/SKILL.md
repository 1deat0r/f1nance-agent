---
name: execution-trading
description: "Order types, slippage/impact, and the compliance trade log."
version: 0.1.0
author: F1NANCE Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, trading, execution, orders, compliance, risk, audit]
    category: finance
    related_skills: [f1nance, market-data, portfolio-management, quant-methods]
---

# Execution & Trading

The execution lens: a good idea, badly executed, is a loss. This skill covers
how an order should be structured, what it costs to trade, and how every
decision is written down — the compliance trade log that makes the trail
auditable.

## The engine (`f1nance/execution/`)

The discipline below is implemented, stdlib-only, in the Phase-4 native core
(see `f1nance/execution/README.md`). Prefer it over hand-rolling:

```python
from f1nance.execution import (
    Order, Side, OrderType, assess, validate_order,
    estimate_cost, Ledger, Decision,
)

o = Order("AAPL", Side.BUY, 100, OrderType.LIMIT, limit_price=190.0)
validate_order(o)                    # raises on structural errors
a = assess(o, market_price=192.0)    # marketable? stop on the right side?
c = estimate_cost(19_000.0, adv=50_000_000.0, spread_bps=5.0)

ledger = Ledger()
d = ledger.record(Decision(
    instrument="AAPL", side="buy", quantity=100, order_type="limit",
    limit_price=190.0, rationale="…", confidence=0.6, risk="…", falsify="…",
))
ledger.fill(d.decision_id, price=189.95)
```

CLI (JSON out):
`python -m f1nance.execution order|impact|ledger|export`.

## Paper first — always

- Nothing touches a real broker until it has run paper for a meaningful
  period and the trade log proves the discipline holds.
- The broker wiring is an API boundary, not a strategy. Model the order
  (`market`/`limit`/`stop`/`stop-limit`) and let the execution layer validate
  and cost it before anything is sent.

## Order types and placement

- **Market** — fills now at the prevailing price; you pay the spread and
  accept slippage. Use when certainty of execution beats price.
- **Limit** — price bound, no worse fill than the limit; the risk is not
  filling. A buy limit above the market (or a sell limit below it) is
  *marketable* — it crosses immediately; treat it as a market order, not a
  patient one.
- **Stop** — becomes a market order when the trigger trades. A buy stop goes
  *above* the market (catch a breakout); a sell stop goes *below* (cut a
  loss). A stop on the far side is already triggered — it is a mis-placement.
- **Stop-limit** — stop trigger plus a limit bound; protects the fill price
  but can leave you unhedged if the market gaps through.

## Slippage and market impact

- **Slippage** is the gap between the signal price and the fill; it is a cost
  you *pay*, not a rounding error. Model it explicitly (at least the
  half-spread per side).
- **Market impact** scales roughly with the square root of participation
  (`notional / ADV`). Small orders are cheap; pushing more than ~10% of ADV
  moves the price against you and the cost is material. The engine raises if
  you try to trade more than the day's entire volume.
- Costs are charged net of gross — a signal that makes 10bp and costs 12bp is
  a loser.

## The compliance trade log (the audit trail)

Every decision is mirrored once, with rationale, confidence, and the loss
case, and *never edited or deleted*:

1. **Record before you act.** Rationale, confidence (0..1, or high/medium/
   low), loss case, and falsification condition are mandatory.
2. **Rejection is recorded, not dropped.** A decision that fails a compliance
   rule (missing rationale, out-of-range confidence, oversize notional) is
   written as `rejected` with its violations — the trail shows the attempt.
3. **Status is derived, never overwritten.** Fills and cancels are appended as
   events; the current status of a decision is folded from the stream.
4. **A rejected decision cannot be filled.** The ledger refuses; you cannot
   quietly execute an order the rules said no to.

## Delivery

State the order, its expected cost (spread + impact + fees, in bps and
currency), and its execution risk. Confirm the decision is in the log with a
`decision_id`. If a trade is proposed but not logged, it did not happen.

## Pitfalls

- **Marketable limit orders** the sender thought were patient — a buy limit
  above the ask is an immediate fill, not a bargain.
- **Ignoring the cost of size** — a backtested edge in a name you cannot trade
  at size without impact is not an edge.
- **Stop mis-placement** — a sell stop above the market (or buy stop below)
  triggers immediately; it is a fat-finger, not a hedge.
- **Trading before logging** — an order with no rationale in the ledger is a
  decision that was never made; it cannot be defended later.
