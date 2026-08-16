# F1NANCE Harness Architecture

This is the design of the harness — how one sovereign agent becomes a full
finance desk. It is the contract the skills implement and the roadmap extends.

## The core idea

F1NANCE is not a collection of role-prompts. It is a **routing layer** over a
set of **capability domains**, each backed by **real data sources** and
**real methodology**, wrapped in a **risk-and-honesty guardrail** that is
non-negotiable. A task enters the harness, is routed to one or more domains,
is executed against live data, and leaves as a thesis with a confidence level
and a named loss case.

```
task ──► route ──► gather data ──► analyze ──► produce artifact ──► verify ──► deliver
              │            │            │              │              │
        domain(s)    market-data    domain       model/memo/deck   guardrail
                        skill        skill(s)
```

## Role taxonomy → capability domains

Twelve roles collapse into six capability domains. The harness routes to a
domain, not to a persona.

| Capability domain | Roles it serves | Core deliverable |
|---|---|---|
| **Advisory** | Financial Advisor, Investment Advisor | Goals, risk capacity vs. tolerance, allocation, plan |
| **Corporate Finance & Accounting** | Accountant, CFO | 3-statement truth, close, FP&A, capital allocation, cash-flow |
| **Markets & Trading** | Macro S&T, Equities S&T | Rates/FX/credit/equity/vol views, trade ideas, execution risk |
| **Investment Banking** | M&A Director, IB Director, Senior Banker | Valuation, deal structuring, process, strategic optionality |
| **Asset Management** | Hedge Fund Manager, Portfolio Manager | Construction, risk/factor models, attribution, drawdown |
| **Quantitative** | Quantitative Analyst | Models, stats, backtesting, pricing — validated, not overfit |

## Tool layer (what the domains run on)

| Need | Tool | Backed by |
|---|---|---|
| Equity prices, fundamentals, options | `market-data` skill | yfinance (Yahoo), stooq |
| Macro series (GDP, CPI, rates, money) | `market-data` skill | FRED (fredgraph.csv), central banks |
| Filings, 10-K/10-Q/8-K, insider | `market-data` skill | SEC EDGAR |
| News, research, sentiment | web_search / web_extract | keyless DDG backend |
| Computation, models, backtests | execute_code / terminal | Python + numpy/pandas/scipy |
| Reports, memos, decks, models | pdf/docx/xlsx/powerpoint skills | python-pptx, openpyxl, reportlab |
| Numbers in → tables out | xlsx/csv skills | openpyxl / csv |
| Orders, execution costs, trade log | `execution-trading` skill | `f1nance/execution` engine (stdlib) |
| Bond pricing, yield curves, duration | `fixed-income` skill | `f1nance/fixed_income` engine (stdlib) |
| Options pricing, Greeks, implied vol | `derivatives` skill | `f1nance/derivatives` engine (stdlib) |
| Limits, stress tests, VaR backtesting | `risk-management` skill | `f1nance/risk_management` engine (stdlib) |
| Merger accretion, synergies, LBO | `m-and-a` skill | `f1nance/m_and_a` engine (stdlib) |
| Whole-deal scoring (valuation→M&A→risk) | `deal-memo` skill | `f1nance/deal_memo` engine (stdlib) |

## The guardrail layer (cross-cutting, always on)

These come from the SOUL and are enforced by the umbrella `f1nance` skill on
every task, in every domain:

1. **No fabrication.** Never invent a price, a quote, a return, a filing, or a
   data point. If the source is unavailable, say so.
2. **Confidence calibration.** Every view carries a confidence level and the
   specific facts that would falsify it. High certainty without evidence is an
   error.
3. **Risk before return.** Every recommendation names the loss case and its
   size before the upside.
4. **Suitability.** Sizing fits 1deat0r's objectives, horizon, and risk
   capacity — never activity for its own sake.
5. **Not-a-license.** Output is analysis and judgment, never a claim to be a
   registered adviser, broker-dealer, or CPA.
6. **No market abuse.** No trading on MNPI, no manipulation, refusal of any
   instruction that asks for it.

## Skill map

| Skill | Domain(s) | Status |
|---|---|---|
| `f1nance` (umbrella) | All — routing + guardrails | ✅ v0.01 |
| `market-data` | All (the data substrate) | ✅ v0.2.0 |
| `valuation` | IB, Asset Mgmt, Advisory | ✅ v0.01 |
| `portfolio-management` | Asset Mgmt, Advisory | ✅ v0.2.0 |
| `financial-statement-analysis` | Corp Finance, IB, Advisory | ✅ v0.01 |
| `macro-analysis` | Markets & Trading, Advisory | ✅ v0.01 |
| `quant-methods` | Quantitative, Asset Mgmt | ✅ v0.2.0 |
| `m-and-a` (deal process & structuring) | IB | ✅ v0.1.0 |
| `deal-memo` (whole-deal scoring) | IB, all | ✅ v0.1.0 |
| `fixed-income` (bonds, yield curves, credit) | Markets & Trading, Quant, Asset Mgmt | ✅ v0.1.0 |
| `derivatives` (options pricing, greeks, hedging) | Quant, Trading | ✅ v0.1.0 |
| `risk-management` (VaR, stress, limits) | All | ✅ v0.1.0 |
| `execution-trading` (orders, costs, trade log) | Trading, all | ✅ v0.1.0 |

## The native core (`f1nance/`) vs. the Hermes profile

- **`f1nance/` (this repo)** is canonical: the SOUL, the architecture, the
  skills, the roadmap. It is version-controlled and is what makes the fork a
  fork.
- **`~/.hermes/profiles/f1nance/`** is the projection: the runtime identity
  (`SOUL.md`) and installed skills that Hermes actually loads. It is derived
  from `f1nance/`, not the other way around.

Phase 5 delivered both halves of that move: `f1nance/desk/` (the multi-agent
coordination layer — five seats, one verdict, executor-injected so the
coordination logic is Hermes-free) and `f1nance/core/` (the store-first
memory/decision substrate, modeled on the 3V0 Agent's `3v0/`: an append-only
provenance store plus a projector that renders the active facts into a
derived view). The profile remains a derived view; the repo remains the body.

The desk's `Executor` seam is now wired live: `f1nance/desk/live.py` is a
Hermes-free model executor (`ModelClient` over stdlib `urllib`, DeepSeek by
default) behind the same callable, with the `live` CLI command and a
bounded-retry parser that refuses to fabricate a finding. This is the executor
the standalone agent runs at Phase 6, so the desk can go live today without
reintroducing Hermes coupling.

**End state — delivered.** F1NANCE is its own agent, separate from Hermes
Agent: `f1nance/agent/` is the standalone runtime (own entry point, tool
registry, and memory/decision substrate) with no Hermes dependency. The
Hermes profile is a bootstrap convenience that is discarded on the way out —
never a load-bearing dependency. The `f1nance/` core is Hermes-independent by
design, so the body is portable and the chassis is not mourned.
