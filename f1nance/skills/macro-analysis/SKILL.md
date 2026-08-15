---
name: macro-analysis
description: "Build a macro view: growth/inflation/policy framework, rates and the yield curve, FX, credit spreads, central-bank reaction functions, data calendar."
version: 0.1.0
author: F1NANCE Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, macro, rates, fx, inflation, central-banks, credit, trading]
    category: finance
    related_skills: [f1nance, market-data, quant-methods]
---

# Macro Analysis

The macro sales & trading lens: read the growth / inflation / policy cycle and
turn it into views on rates, FX, and credit — each with a confidence level and
a falsifier.

## The framework: one cycle, three forces

Everything reduces to **growth**, **inflation**, and the **policy reaction**
to both. The market is a machine for pricing the future path of these three.

1. **Growth** — where are we in the cycle (early/mid/late/recession)? Read
   GDP, PMIs, employment, retail sales, industrial production, consumer
   confidence.
2. **Inflation** — headline vs. core; PCE (the Fed's target) vs. CPI; wage
   growth and inflation expectations (breakevens, surveys).
3. **Policy** — what does the central bank care about, and what is its
   reaction function? Fed: dual mandate (employment + ~2% PCE). ECB: price
   stability. BoJ: the outlier that has fought deflation.

## Rates & the yield curve

- **Short end** prices the policy path; **long end** prices growth +
  inflation + term premium.
- **Curve shape:** steepening bull/bear, flattening, inversion. A
  2s10s inversion (2y > 10y) has preceded recessions — a warning, not a
  trade signal by itself.
- **Real vs. nominal:** real yield = nominal − breakeven. Falling real yields
  with rising breakevens = stagflationary read; the opposite = disinflation.
- **Term premium** is the extra yield for duration risk — unobservable,
  estimated; say whose estimate you use (e.g. ACM model) or avoid it.

## FX

- **Carry:** buy the high-yielding currency, fund in the low — the classic
  carry trade, and it blows up in risk-off (carry unwinds are violent).
- **Purchasing power parity (PPP):** long-run anchor, useless for timing.
- **Interest-rate parity:** forward = spot × (1+i_dom)/(1+i_for); the forward
  is a price, not a forecast.
- **Real exchange rates and current accounts** drive the slow trends; **rate
  differentials** drive the fast moves. A currency is the relative price of
  two monetary policies.

## Credit

- **Spreads** (OAS) price default + liquidity + risk appetite. Tight spreads =
  complacency; wide = stress.
- Watch **HY vs. IG spread**, **HY OAS vs. its history**, and the
  **front-end** (money markets) — credit cracks show up there first.
- Credit is a short-vol / short-put trade: steady small carry, occasional
  large loss. Size accordingly.

## Central-bank reaction functions

- **Fed:** dual mandate, dot plot, "data-dependent", long and variable lags.
- **ECB:** single mandate (price stability), fragmented banking system,
  politically constrained.
- **BoJ:** yield-curve control history, owns huge JGB/ETF positions, a
  policy-exit risk the whole world prices.
- Every bank now: forward guidance is data-conditional — trade the *data*,
  not the *guidance*.

## The data calendar (the tradable events)

CPI, PCE, Nonfarm Payrolls, FOMC/ECB/BoJ decisions, GDP, PMIs, retail sales.
Know what's on this week and the consensus (Bloomberg/Reuters consensus via
web_search). The market doesn't trade the number — it trades the number
**vs. consensus vs. what's already priced**.

## Building the view (repeatable)

1. Write down the **current state** of growth/inflation/policy with data and
   dates (use `market-data` → FRED).
2. State the **consensus** and where you **differ**.
3. Translate the difference into **trades** (steepener, long/short a
   currency, credit vs. equity, duration under/overweight).
4. Attach a **confidence** and a **falsifier** (the data release or event
   that would prove you wrong).
5. Follow the `f1nance` delivery block.

## Pitfalls

- **Confusing levels with changes.** Markets price *change*, not the level of
  growth or inflation.
- **The "good news is bad news" flip.** Strong data can be bad for risk assets
  if it means higher-for-longer rates. State the conditioning explicitly.
- **Recency bias.** The last regime (low rates, disinflation) is not the
  default; the next decade may not look like the last.
- **Single-indicator certainty.** One CPI print is noise; a trend across
  prints, wages, and expectations is signal.
- **Central-bank over-personalization.** Trade the reaction function, not a
  personality cult around any chair.
