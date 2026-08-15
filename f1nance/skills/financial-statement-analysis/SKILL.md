---
name: financial-statement-analysis
description: "Read the 3 statements like an accountant/CFO: ratios, DuPont, cash-flow truth, quality of earnings, red flags."
version: 0.1.0
author: F1NANCE Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, accounting, financial-statements, ratios, dupont, cfo, red-flags]
    category: finance
    related_skills: [f1nance, market-data, valuation]
---

# Financial Statement Analysis

The accountant / CFO lens. Before any valuation or trade, know whether the
numbers are real and what they actually say about the business.

## The three statements and how they link

- **Income statement** — revenue → EBITDA → EBIT → net income (a period's
  earning performance; accrual-based, not cash).
- **Balance sheet** — assets = liabilities + equity (a point-in-time snapshot).
- **Cash flow statement** — operating / investing / financing cash flows
  (reconciles accrual earnings to actual cash movement).

Linkages: net income (IS) → retained earnings (BS); net income + non-cash +
working-capital changes ≈ operating cash flow (CF); capex (CF investing) → PP&E
(BS) → depreciation (IS). If these don't reconcile, something is wrong — dig.

## Ratio families

**Liquidity** — current = CA/CL; quick = (cash + AR + ST investments)/CL;
operating cash flow / current liabilities.

**Solvency / leverage** — debt/equity; debt/EBITDA (a payback horizon: >4–5×
is stretched for most industries); interest coverage = EBIT/interest (>2× is
the floor of comfort); net debt = total debt − cash.

**Profitability** — gross margin, operating margin, net margin, ROE, ROA,
ROIC (the one that matters most for value creation: is the business earning
above its cost of capital?).

**Efficiency** — DSO (AR/revenue·365), DIO (inventory/COGS·365), DPO
(AP/COGS·365), cash conversion cycle = DSO + DIO − DPO; asset turnover.

## DuPont decomposition

```
ROE = Net margin × Asset turnover × Equity multiplier
    = (NI/Sales) × (Sales/Assets) × (Assets/Equity)
```

This separates **operating quality** (margin), **efficiency** (turnover), and
**leverage** (multiplier). A rising ROE driven only by the multiplier is
risk, not skill.

## Cash-flow truth

- **Earnings quality:** compare net income to operating cash flow over
  several years. A persistent, widening gap (income up, OCF flat/down) is a
  red flag — earnings are accruals, not cash.
- **Free cash flow** = OCF − capex. This is what can actually service debt
  and fund buybacks/dividends.
- **Working-capital build:** if receivables and inventory are growing faster
  than revenue, the company is financing its own growth — watch it.

## Red flags (checklist)

1. Revenue growing while operating cash flow shrinks (aggressive revenue
   recognition).
2. DSO or DIO rising sharply (channel-stuffing, stale inventory).
3. Frequent restatements, auditor changes, or a going-concern note.
4. Non-GAAP metrics that only ever add back and never subtract.
5. Off-balance-sheet obligations (operating leases pre-ASC 842, guarantees,
   earnouts) or large other-financing line items.
6. Related-party transactions and sudden changes in accounting policy.
7. Big "other income" or one-offs flattering the bottom line.

## How to actually do it

1. Pull 5–10 years of statements (`market-data` → yfinance or SEC EDGAR).
2. Common-size everything (as % of revenue / % of assets) to see trends.
3. Compute the ratio families year over year; find the inflection points.
4. Read the MD&A and footnotes for the *why* — ratios tell you *what*.
5. Deliver a one-page view: trends, quality of earnings, leverage comfort,
   and the 2–3 things that would change the read.

## Pitfalls

- **One year proves nothing.** Always trend; a single-year ratio is a
  snapshot, not a pattern.
- **Cross-industry comparison is noise.** Banks, software, and industrials
  have structurally different balance sheets; compare within a peer set.
- **EBITDA is not cash.** It ignores capex, working capital, interest, and
  tax — four things that matter.
- **Restated vs. as-reported.** Know whether figures are point-in-time or
  restated; acquisitions and accounting changes rewrite history.
