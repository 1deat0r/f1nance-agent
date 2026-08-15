# F1NANCE Execution & Compliance Layer

The Phase-4 counterpart to `f1nance/data`, `f1nance/portfolio`, and
`f1nance/quant`. Where those layers guarantee a number is never fetched-,
arithmetically-, or statistically-fabricated, this package guarantees an
*order is never silently executed*: every decision is validated, costed, and
mirrored in an append-only compliance ledger with its rationale, confidence,
and loss case.

Hermes-independent by design: standard library only (`dataclasses`, `enum`,
`datetime`, `json`) — no numpy, no pandas, no broker SDK, no Hermes. Runs on
any Python 3.9+.

## Modules

| Module | What it does |
|---|---|
| `orders` | Order model (market/limit/stop/stop-limit), structural validation, and marketability / stop-side assessment against a market price |
| `impact` | Slippage + market-impact model: half-spread per side, square-root impact over participation, fees — a trade is costed before it is placed |
| `ledger` | The append-only compliance trade log: every decision recorded once (rationale + confidence + loss case), status derived from an immutable event stream, and a compliance gate that rejects rather than drops |

## Use

As a library:

```python
from f1nance.execution import (
    Order, Side, OrderType, assess, validate_order,
    estimate_cost, Ledger, Decision,
)

o = Order("AAPL", Side.BUY, 100, OrderType.LIMIT, limit_price=190.0)
validate_order(o)                       # raises on structural errors
a = assess(o, market_price=192.0)       # marketable? stop on the right side?

c = estimate_cost(19_000.0, adv=50_000_000.0, spread_bps=5.0)
c.total_bps, c.total_cost               # what it costs to trade

ledger = Ledger()
d = ledger.record(Decision(
    instrument="AAPL", side="buy", quantity=100, order_type="limit",
    limit_price=190.0, rationale="momentum continuation", confidence=0.6,
    risk="break of the 50-day; ~-8%", falsify="close below the 200-day",
))
ledger.fill(d.decision_id, price=189.95)   # append-only: status is derived
ledger.status_of(d.decision_id)            # "filled"
```

From the CLI (all JSON on stdout):

```bash
f1nance/.venv/bin/python -m f1nance.execution order spec.json
f1nance/.venv/bin/python -m f1nance.execution impact spec.json
f1nance/.venv/bin/python -m f1nance.execution ledger spec.json --out ledger.jsonl
f1nance/.venv/bin/python -m f1nance.execution export ledger.jsonl
```

## Conventions (trust the trail, not the assumption)

- **Confidence is numeric** (`0.0`–`1.0`) and canonical; `high`/`medium`/`low`
  are accepted aliases (`0.8`/`0.5`/`0.2`) and `confidence_label()` renders the
  label back for display.
- **Costs are in basis points**; `total_cost` is currency (`notional × bps /
  10,000`). The spread charge is the *half-spread* (one side).
- **Market impact is square-root law**: `sigma_daily_bps × coefficient ×
  sqrt(participation)`. Participation above **10% of ADV** is flagged
  `impact_zone`; above **100%** raises (you cannot trade more than the day's
  volume).
- **The ledger is append-only.** Decisions are never edited or deleted; fills
  and cancels are appended events, and `status_of()` *derives* the current
  status from the stream.
- **Rejection is recorded, not dropped.** A decision that fails a compliance
  rule (missing rationale, out-of-range confidence, oversize notional) is
  written with `status="rejected"` and its `violations` — and a rejected
  decision refuses to be filled.
- **Degenerate input raises**: non-positive quantity or prices, a price
  without its order type, negative costs, participation above 100%.

## What it deliberately does not do

- **No broker connectivity.** This layer models and logs execution; it does
  not reach a live venue. Wiring a real broker (or a paper venue) is a
  separate, deliberate step — and it must happen *behind* this ledger, never
  around it.
- **No price prediction** — feed it market data from `f1nance.data` and let
  `f1nance.quant` decide what to trade; this layer handles how it is executed
  and how the decision is recorded.
- **No deletion.** There is no `delete`/`update` API by design. A wrong entry
  is corrected by appending a cancellation or a superseding event, so the
  trail always shows what actually happened.

## Test

```bash
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests -v
```

Offline; no network, no broker, no Hermes.
