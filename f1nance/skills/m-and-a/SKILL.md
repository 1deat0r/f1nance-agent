---
name: m-and-a
description: "Merger accretion/dilution, synergy valuation, and LBO."
version: 0.1.0
author: F1NANCE Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, m-and-a, investment-banking, accretion, synergies, lbo, deal-structuring]
    category: finance
    related_skills: [f1nance, valuation, financial-statement-analysis, execution-trading]
---

# M&A

The deal lens: once a target is valued, does the deal make sense? Three
questions answered with numbers — *does the merger add to earnings*
(accretion/dilution), *do the synergies pay for the premium* (synergy
valuation and break-even), and *what does a levered buyer earn* (LBO). Answer
all three on the same inputs, and refuse to report a number you did not
compute.

## The engine (`f1nance/m_and_a/`)

The discipline below is implemented, stdlib-only, in the Phase-10 native core
(see `f1nance/m_and_a/README.md`). Prefer it over hand-rolling:

```python
from f1nance.m_and_a import accretion_dilution, synergy_value, synergy_breakeven, lbo

r = accretion_dilution(500, 100, 120, 2000, 1000, 1000, 50, 0.25,
                       cost_synergies=80, new_debt_rate=0.05)   # +7.1% accretive
s = synergy_value(100, 0, 0, 0.25, 0.10, 2, 50, 400)            # covered
b = synergy_breakeven(400, 50, 0.25, 0.10, 2)                   # ~$62.9 required
m = lbo(1000, 200, 30, 700, 100, 0.05, 5, 0.60, 8.0, 0.06, tax_rate=0.25)
```

CLI (JSON out): `python -m f1nance.m_and_a accretion|synergies|breakeven|lbo spec.json`.
The engine refuses to fabricate: a cash/stock split that does not sum to the
purchase price raises, `r <= g` raises, a non-positive equity check raises.

## When to use

- Deciding whether a proposed merger is accretive or dilutive to the acquirer,
  and by how much — the first question 1deat0r's banker asks.
- Valuing the synergy case: does the premium the buyer is paying get covered by
  the synergies, and what run-rate would be needed just to break even?
- Modeling a leveraged buyout: how much equity, how much debt, how fast it pays
  down, and what the sponsor earns (MOIC/IRR).

Not here: *standalone valuation* (that is `valuation` — DCF/comps/precedent),
*reading the target's three statements* (that is
`financial-statement-analysis`), or *structuring the order to build a position*
(that is `execution-trading`). This skill prices the *deal*, not the company.

## Accretion / dilution

- The bridge: **pro-forma NI = NI_acquirer + NI_target + (synergies − financing
  cost) × (1 − tax)**; **pro-forma EPS = pro-forma NI / (shares + new shares)**.
- Stock consideration issues new shares at the acquirer's share price; cash
  consideration is funded by cash on hand (forgoing interest) and/or new debt
  (incurring interest). Both financing legs are tax-affected.
- Report the **absolute** ($/share) accretion and the **relative** (%); when the
  acquirer's standalone EPS is zero or negative the % sign is meaningless — use
  the `accretive` flag and the dollar amount instead.
- A deal that does not balance (cash + stock ≠ price) is not a deal — refuse it.

## Synergies

- Synergies are a **pre-tax run-rate**, tax-affected, ramped in over a few
  years, then grown in perpetuity at a rate below the discount rate.
- Revenue synergies must flow through a **margin**; only the incremental profit
  is a synergy, not the gross revenue.
- **Net synergy value = gross PV − integration costs − premium paid.** If it is
  negative, the buyer is paying for synergies it will not realize — say so.
- **Break-even** inverts it: the run-rate synergies required to exactly cover
  the premium + integration costs. That is the number that tells 1deat0r how
  much cost-cutting (or cross-sell) the deal has to actually deliver.

## LBO

- **Sources & uses must balance**: uses = enterprise value + fees; equity
  check = uses − entry debt. A non-positive equity check means the deal is
  over-levered — it does not work.
- Each year, free cash flow repays debt. FCF = EBITDA × margin − cash interest;
  debt is floored at zero and any excess becomes cash build.
- **Exit equity = exit EV − remaining debt + cash build**; `MOIC = exit equity /
  equity check`; `IRR = MOIC^(1/years) − 1` (all FCF repays debt, no interim
  distributions — the standard base LBO).
- Report **entry vs exit multiple**, the full debt schedule, and both MOIC and
  IRR. MOIC without IRR hides how long the money was out.

## Pitfalls

- **Confusing deal value with standalone value.** Accretion and LBO return are
  driven by the price paid — a bad price accretes a bad deal. Value first, then
  structure.
- **Double-counting synergies.** If you credit synergies in the accretion
  bridge, do not also assume them in the valuation multiple *and* the control
  premium. Pick one place.
- **Ignoring financing.** An all-cash deal is not free money — debt interest or
  forgone cash yield both eat the accretion. Always tax-affect them.
- **A growth rate at or above the discount rate.** A perpetuity needs `r > g`;
  if your synergy case needs `g ≥ r` to look good, it does not look good.
- **MOIC without time.** A 2.0x MOIC over ten years is ~7% IRR; over three years
  it is ~26%. Always quote both.

## Delivery

State the accretion (absolute and relative), the synergy case (gross PV, net of
costs and premium, and the break-even run-rate), and — for a levered deal — the
sources & uses, the debt schedule, and the MOIC/IRR. Name the loss case first:
the premium that is not covered, the synergy run-rate that never materializes,
or the exit multiple that has to be hit for the sponsor to earn its return.
Then the `f1nance` delivery block (thesis + confidence + loss case + data as of).
