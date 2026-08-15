# F1NANCE Roadmap

Phased build of the harness. Each phase is a shippable, verifiable increment.

## Phase 0 — Foundation (this fork) ✅

- Hard-fork Hermes Agent at pinned upstream `main`.
- `f1nance/` native core: SOUL, README, ARCHITECTURE, ROADMAP.
- Umbrella `f1nance` skill (routing + guardrails) and the six core domain
  skills.
- Runtime profile `~/.hermes/profiles/f1nance/` projected from the repo.

## Phase 1 — Data substrate hardening ✅

- `f1nance/data/` fetch/cache layer: stdlib-first (stooq, FRED, EDGAR),
  yfinance optional (own `f1nance/.venv`), as-of + source + degraded
  provenance on every result, graceful degradation, no-fabrication guarantee.
- `.gitignore` carve-out so the layer code is tracked and `f1nance/data/cache/`
  is not.
- 29 offline unit tests (`f1nance/tests/`); live-verified against yfinance,
  FRED, and SEC EDGAR.
- Free sources only, with graceful degradation when a source is down.

## Phase 2 — Portfolio & risk engines ✅

- `f1nance/portfolio/` engine, stdlib-only (no numpy, no Hermes):
  - `positions` — `Position`/`Portfolio`: weights, long/short/gross/net
    exposure, FX conversion, cash drag, rebalance trades.
  - `risk` — returns, vol, Sharpe/Sortino, historical + parametric VaR/CVaR,
    beta/correlation, drawdown, concentration (HHI / effective N).
  - `attribution` — Brinson-Fachler allocation / selection / interaction
    (sums exactly to active return).
- Every metric raises on degenerate input (missing FX rate, zero variance,
  mismatched series, weights that don't sum to 1.0) rather than fabricating.
- 62 offline unit tests added (91 total, all green); `value`/`risk`/`attr`
  CLI with JSON output.

## Phase 3 — Quant & backtesting ✅

- `f1nance/quant/` engine, stdlib-only (no numpy, no scipy, no Hermes):
  - `linear` — OLS + ridge regression with full inference (coefficients,
    standard errors, t-statistics, R² / adjusted R², residual stddev) over a
    minimal stdlib linear-algebra core. Singular (collinear) designs raise
    rather than returning a garbage fit.
  - `factors` — CAPM and multi-factor (Fama-French / Carhart) exposure models
    (alpha, per-factor beta + t-stat, residual/idiosyncratic vol),
    cross-sectional z-score and percentile rank, trailing-return momentum and
    a point-in-time momentum predictor.
  - `backtest` — a walk-forward backtesting harness: rolling/expanding origin,
    explicit transaction costs + slippage on turnover, structural look-ahead
    guards (the predictor is handed only point-in-time data), and honest
    in-sample (flagged `lookahead=True`) vs out-of-sample reporting.
- Every metric raises on degenerate input (collinear regressors, constant
  response, mismatched series, weights that don't sum to 1.0, a held asset
  with no return, a cross-section with zero variance).
- 49 offline unit tests added (140 total, all green); `capm`/`ff`/`backtest`/
  `momentum` CLI with JSON output.

## Phase 4 — Execution & compliance ✅

- `f1nance/execution/` engine, stdlib-only (no numpy, no broker SDK, no
  Hermes):
  - `orders` — order model (market/limit/stop/stop-limit) with structural
    validation and marketability / stop-placement assessment against a market
    price.
  - `impact` — slippage + market-impact model (half-spread per side,
    square-root impact over participation, fees), participation above 100% of
    ADV raising and above 10% flagged as the impact zone.
  - `ledger` — the append-only compliance trade log: every decision mirrored
    once with rationale, confidence, and loss case; status derived from an
    immutable event stream; a compliance gate that records (never drops)
    rejections and refuses to fill them.
- `execution-trading` skill (v0.1.0) fronting the engine.
- Every metric raises on degenerate input (non-positive quantity/prices, a
  price without its order type, negative costs, participation > 100%).
- 64 offline unit tests added (204 total, all green); `order`/`impact`/
  `ledger`/`export` CLI with JSON output.

## Phase 5 — The desk (multi-agent) ✅

- `f1nance/desk/` — the multi-agent coordination layer, stdlib-only: a
  five-seat roster (PM, trader, quant, banker, CFO) over the six capability
  domains, deterministic routing, and a coordinator that folds each seat's
  `Finding` (thesis + stance + confidence + loss case + falsification) into a
  single `Verdict` with consensus/dissent surfaced and every loss case
  preserved. A seat's judgment is produced by an injectable `executor` — in
  tests and the offline CLI it is scripted, in a live runtime it is a model
  call or a delegated subagent; the coordination logic is Hermes-free.
- `f1nance/core/` — the store-first evolution loop, stdlib-only: an
  append-only, provenance-aware memory/decision store (supersede/retract,
  never overwrite) plus a projector that renders the active facts into a
  derived view. The repo stays the body; the Hermes profile stays a derived
  projection.
- 58 offline unit tests added (262 total, all green); `seats`/`route`/`run`
  and `record`/`retract`/`export`/`history`/`render` CLIs with JSON output.

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
