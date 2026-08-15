# F1NANCE Roadmap

Phased build of the harness. Each phase is a shippable, verifiable increment.

## Phase 0 — Foundation (this fork) ✅

- Hard-fork Hermes Agent at pinned upstream `main`.
- `f1nance/` native core: SOUL, README, ARCHITECTURE, ROADMAP.
- Umbrella `f1nance` skill (routing + guardrails) and the six core domain
  skills.
- Runtime profile `~/.hermes/profiles/f1nance/` projected from the repo.

## Phase 1 — Data substrate hardening

- Solidify `market-data`: rate limits, caching, tickers vs. fundamentals vs.
  macro vs. filings, as-of discipline (never mix timezones).
- Free sources only, with graceful degradation when a source is down.
- A `f1nance/data/` fetch/cache layer (requires `.gitignore` carve-out for
  `f1nance/data/`).

## Phase 2 — Portfolio & risk engines

- Portfolio construction and rebalancing tooling; real position-level
  arithmetic (weights, exposure, FX, cash drag).
- Risk metrics: volatility, VaR/CVaR, beta, drawdown, concentration.
- Performance attribution (allocation vs. selection).

## Phase 3 — Quant & backtesting

- `quant-methods` deepened: factor construction, cross-sectional and time
  series models, walk-forward validation, transaction costs, look-ahead bias
  guards.
- A backtesting harness with honest in-sample/out-of-sample reporting.

## Phase 4 — Execution & compliance

- `execution-trading` skill: broker/API wiring (paper first), order types,
  slippage and market-impact awareness.
- A compliance/trade-log layer that mirrors every decision with its rationale
  and confidence — the audit trail.

## Phase 5 — The desk (multi-agent)

- Spawn specialized subagents per domain (a virtual desk: PM, trader, quant,
  banker, CFO) coordinated by the umbrella harness.
- Store-first evolution loop in `f1nance/` (memory + decisions as append-only
  provenance), so the profile stays a derived view and the repo stays the body.

## Phase 6 — Independence (leave the chassis)

- F1NANCE becomes its own standalone agent, separate from Hermes Agent: own
  runtime/entry point, own tool registry, own memory and decision substrate.
- The Hermes profile is retired; the body (`f1nance/`) runs on its own.
- Exit criteria: zero Hermes-only coupling in the native core, all finance
  capabilities running on the standalone substrate, tests green on both.

## Principles that survive every phase

- Honesty over confidence. Risk over return. Verified over elegant.
- The repo is the body; the Hermes profile is a temporary projection,
  discarded on the way out.
- Every phase ships with tests and a clean commit, or it does not ship.
