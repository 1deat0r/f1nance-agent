# F1NANCE M&A Engine

The Phase-10 layer that prices the *deal*, not the company. Where the
`valuation` skill (and `f1nance.portfolio`/`f1nance.quant` methodology) arrives
at a standalone value, this package works the deal mechanics: the EPS bridge
(accretion/dilution), the synergy bet that justifies the premium, and the
leveraged-buyout return. It is the Investment-Banking domain made checkable.

Hermes-independent by design: standard library only (`math`, `dataclasses`) —
no numpy, no pandas, no scipy, no Hermes. Runs on any Python 3.9+.

## Modules

| Module | What it does |
|---|---|
| `accretion_dilution` | `accretion_dilution` → pro-forma EPS and accretion/dilution of a cash/stock merger, with the financing and synergy bridge |
| `synergies` | `synergy_value` (PV the run-rate synergies, net of integration costs + premium) and `synergy_breakeven` (the run-rate required to break even) |
| `lbo` | `lbo` → sources & uses, a year-by-year debt schedule, the exit, and the sponsor's MOIC/IRR |

## Use

As a library:

```python
from f1nance.m_and_a import accretion_dilution, synergy_value, synergy_breakeven, lbo

# accretion/dilution — $2,000 deal, 50/50 cash/stock, $80 synergies
r = accretion_dilution(500, 100, 120, 2000, 1000, 1000, 50, 0.25,
                       cost_synergies=80, new_debt_rate=0.05)
#   pro-forma EPS ~5.354, +7.1% accretive

# synergies — $100 pre-tax run-rate, ramped over 2 years, 10% discount
s = synergy_value(100, 0, 0, 0.25, 0.10, 2, 50, 400)   # net ~265.9, covered

# break-even — what run-rate synergies justify a $400 premium?
b = synergy_breakeven(400, 50, 0.25, 0.10, 2)          # ~$62.9 pre-tax

# LBO — $1,000 EV at 8x, $700 debt, 5-year hold, exit 8x
m = lbo(1000, 200, 30, 700, 100, 0.05, 5, 0.60, 8.0, 0.06, tax_rate=0.25)
#   equity check $330, MOIC ~1.60x, IRR ~9.9%
```

From the CLI (all JSON on stdout):

```bash
f1nance/.venv/bin/python -m f1nance.m_and_a accretion spec.json
f1nance/.venv/bin/python -m f1nance.m_and_a synergies spec.json
f1nance/.venv/bin/python -m f1nance.m_and_a breakeven spec.json
f1nance/.venv/bin/python -m f1nance.m_and_a lbo spec.json
```

## Conventions (trust the number, not the assumption)

- Money is one currency throughout. Rates, tax, and margins are **decimals**
  (`0.25` = 25%).
- **Accretion** is reported absolute ($/share) and relative (%); the relative
  term is `None` when standalone EPS is zero or negative, where the sign is
  meaningless. The `accretive` flag is the unambiguous reading.
- **Synergies** are pre-tax run-rate, ramped linearly to full run-rate over
  `ramp_years`, then grown in perpetuity (Gordon growth, requires `r > g`).
  Revenue synergies flow through a `revenue_margin`.
- **LBO IRR** is the closed-form `moic ** (1/years) - 1` — valid because all
  FCF repays debt (no interim distributions), the standard base LBO.
- Degenerate input **raises**: a cash/stock split that does not sum to the
  purchase price, `r <= g`, an equity check that is non-positive (over-levered
  deal), a tax rate outside `[0, 1)`.

## What it deliberately does not do

- No **standalone valuation** — DCF, comps, and precedent transactions belong
  to the `valuation` skill. This package prices the deal on top of a value.
- No **deal-process / negotiation modeling** — the skill guides process; the
  engine computes the numbers.
- No **interim LBO distributions** — the model assumes all FCF repays debt and
  the sponsor is paid at exit. A dividend-recap extension is a follow-up.
- No **market data** — all inputs are computed upstream.

## Test

```bash
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests -v
```

Offline; no network, no Hermes.
