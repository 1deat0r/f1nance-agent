---
name: valuation
description: "Value a company or asset: DCF (WACC, terminal value), trading comps (EV/EBITDA, P/E), precedent transactions, sum-of-parts."
version: 0.1.0
author: F1NANCE Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, valuation, dcf, comps, m-and-a, investment-banking, equity]
    category: finance
    related_skills: [f1nance, market-data, financial-statement-analysis]
---

# Valuation

Valuing a company or asset. Three workhorse methods plus sum-of-parts. Use
more than one and reconcile — no single method owns the truth.

## 1. DCF (intrinsic value)

Unlevered free cash flow, discounted at WACC.

```
UFCF = EBIT × (1 − tax) + D&A − capex − ΔNWC
EV   = Σ UFCF_t / (1+WACC)^t + TV / (1+WACC)^n
TV   = UFCF_{n+1} / (WACC − g)     # Gordon growth; g < WACC
Equity value = EV − net debt − minority interest + cash/equivalents
```

- **WACC** = E/V·Re + D/V·Rd·(1−t). Re via CAPM: `Re = Rf + β·(ERP)`.
  Use the 10y Treasury as Rf, an equity risk premium ~4.5–6% (state your
  choice), and a beta either from a source or relevered from peers:
  `β_u = β_l / (1 + (1−t)·D/E)`, then relever to the target's D/E.
- **Project 5–10 years** of UFCF from the income statement; grow revenue by a
  defensible rate, fade margins toward a terminal operating margin, keep capex
  ≥ D&A over the long run.
- **Terminal growth** `g` ≈ long-run nominal GDP (~2–3%); do not exceed it for
  a mature firm. The TV is usually 60–80% of EV — that is the model's biggest
  assumption, so sensitivity-test it hardest.
- **Deliver sensitivity**: vary WACC ±100bp and g ±50bp, present an EV bridge.

## 2. Trading comparables (relative value)

```
EV = market cap + total debt + pref + minority interest − cash
EV/EBITDA, EV/Revenue, P/E, P/B, PEG, FCF yield
```

- Pick 5–8 genuinely comparable peers (same industry, similar size/growth/
  margin profile). Exclude outliers and explain any exclusion.
- Use **forward** estimates when available and say so; trailing is backward.
- EBITDA is not cash flow — add back only real non-cash items; do not let a
  comps multiple on low-quality EBITDA mask leverage.
- Compute the comp set's median and quartiles, not just the mean (one outlier
  distorts a mean).

## 3. Precedent transactions (control value)

Same EV multiples, but on **actual closed M&A deals** in the sector, and
including a **control premium** (typical 20–40% over unaffected price).

- Precedents embed synergies and control; they are typically the **highest**
  of the three. Use them for a takeover/floor sense, not a trading value.
- Age matters: a deal from three cycles ago may misprice today's market.

## 4. Sum-of-the-parts (SOTP)

For conglomerates: value each segment separately (segment comps or DCF), sum
the parts, subtract net corporate costs and debt, compare to the whole. If
the parts sum to more than the market price, that is a potential
conglomerate-discount / break-up story — worth stating, not concluding.

## Reconciliation & delivery

Triangulate: DCF gives a range, comps give a market-relative check,
precedents give a control ceiling. Present the football field (all methods'
ranges on one chart) and land on a value range with reasoning. Follow the
`f1nance` delivery block: thesis, confidence, loss case, data-as-of.

## Pitfalls

- **Terminal-value dominance.** If TV is >80% of EV, the "valuation" is
  really a bet on one growth/rate assumption. Say so and stress it.
- **Double-counting.** Don't add synergies to DCF *and* a control premium to
  comps *and* precedent pricing all at once.
- **Mixing real and nominal.** Keep the discount rate and cash flows in the
  same currency (both nominal, or both real).
- **Out-of-date capital structure.** Net debt changes between filing dates;
  recompute from the latest balance sheet.
- **Negative or tiny EBITDA.** Multiples on near-zero denominators are
  meaningless; fall back to EV/Revenue, DCF, or asset value.
- **Confidence calibration.** A valuation is assumptions wearing math. State
  which input, if wrong, moves the answer the most.
