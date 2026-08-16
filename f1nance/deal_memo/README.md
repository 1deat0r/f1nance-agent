# F1NANCE Deal-Memo Engine

The Phase-11 integration layer that turns a deal from *several separate
calculations* into *one scored verdict*. Where the M&A engine answers each
deal-mechanics question on its own (accretion? synergies? LBO return?) and the
risk-management engine answers the risk question, the deal memo chains them —
**valuation inputs → M&A → risk → one recommendation** — and derives the
recommendation from the numbers instead of asserting it.

Hermes-independent by design: standard library only (`math`, `dataclasses`) —
no numpy, no pandas, no scipy, no Hermes. Runs on any Python 3.9+.

## What it produces

`build_deal_memo(spec)` returns a `DealMemo`:

| Field | What it is |
|---|---|
| `accretion` / `synergy` / `breakeven` / `lbo` | the raw M&A engine results (as computed) |
| `limits` / `stress` | the raw risk-management results (as computed) |
| `checks` | the scorecard — one `Check` per gate (`accretion`, `synergy coverage`, `sponsor return`, `risk limits`, `stress budget`), each `pass` / `fail` / `skip` |
| `recommendation` | `favorable` / `adverse` / `inconclusive`, a pure function of the scorecard |
| `not_computed` | the sections that failed to compute and why (never a fabricated number) |
| `loss_cases` | the risk-first loss cases, derived from the failing/limiting numbers |
| `falsify` | the load-bearing assumption that would falsify the memo |

## Use

As a library:

```python
from f1nance.deal_memo import build_deal_memo

memo = build_deal_memo({
    "deal_id": "acme-buys-beta",
    "merger": {
        "acquirer_ni": 500, "acquirer_shares": 100, "target_ni": 120,
        "purchase_price": 2000, "cash_portion": 1000, "stock_portion": 1000,
        "acquirer_share_price": 50, "tax_rate": 0.25,
        "cost_synergies": 100, "new_debt_rate": 0.05,
        "discount_rate": 0.10, "ramp_years": 2,
        "premium_paid": 400, "integration_costs": 50,
    },
    "risk": {
        "nav": 30520,
        "metrics": {"gross_exposure": 1.20},
        "limits": [{"name": "gross exposure", "metric": "gross_exposure",
                    "threshold": 1.50}],
        "exposures": {"equity": 20000.0},
        "scenarios": [{"name": "equity -30%", "shocks": {"equity": -0.30}}],
        "loss_budget": 5000,
    },
})
#   accretion pass (+9.6%), synergy pass (net $265.9), risk limits pass,
#   stress fail (equity -30% loses $6,000 > $5,000 budget) -> adverse
```

From the CLI (JSON on stdout):

```bash
f1nance/.venv/bin/python -m f1nance.deal_memo memo spec.json
```

## Conventions (trust the number, not the assumption)

- Money is one currency throughout. Rates, tax, margins, and shocks are
  **decimals** (`0.25` = 25%, `-0.30` = -30%).
- The **recommendation** is derived, never hand-waved: any `fail` → `adverse`;
  no fail but a `skip` (an LBO without a `hurdle_irr`, a stress test without a
  `loss_budget`) or nothing computable → `inconclusive`; otherwise
  `favorable`.
- **A missing number is a missing check, not a pass.** A section whose inputs
  are absent or degenerate is recorded in `not_computed` with the reason.
- The **sponsor-return** check gates on `hurdle_irr` when supplied; without it
  the LBO is reported but skipped (a return is meaningless without a target).
- The **stress-budget** check gates on `loss_budget` when supplied; without it
  the worst-scenario P&L is reported but skipped.

## What it deliberately does not do

- No **standalone valuation** — DCF, comps, and precedent transactions belong
  to the `valuation` skill; the memo consumes a value as an input, it does not
  value the target.
- No **portfolio construction** — the memo scores a deal, not a book; position
  sizing is `portfolio-management` / `execution-trading`.
- No **negotiation or process** — the skill guides process; the engine computes
  the numbers.
- No **market data** — all inputs are computed upstream.

## Test

```bash
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests -v
```

Offline; no network, no Hermes.
