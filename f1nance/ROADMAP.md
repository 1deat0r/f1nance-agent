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

## Phase 6 — Independence (leave the chassis) ✅

- `f1nance/agent/` — the standalone runtime, stdlib-only, no Hermes imports:
  - `client` — `AgentClient`, an OpenAI-compatible chat-completions client
    with tool calling over stdlib `urllib` (reuses the desk's `ModelError`
    and DeepSeek defaults).
  - `tools` — the `Tool`/`ToolRegistry` and the built-in toolset: 18 tools
    over the six engines (data, portfolio, quant, execution, desk) plus the
    provenance store, each with a JSON schema and an engine-backed handler;
    a failing tool returns an honest `{"error": ...}` rather than crashing.
  - `system` — the system-prompt builder (SOUL + active store facts + the
    working contract).
  - `loop` — the `Agent` tool-calling loop (model → tool calls → results →
    answer), bounded by a step cap that raises rather than inventing.
  - `__main__` — the entry point: `python -m f1nance.agent` (interactive
    REPL), `chat -q "…"` (one-shot), `--list-tools`, `--system`.
- The Hermes profile was the bootstrap fallback; the body (`f1nance/`) runs
  on its own via `python -m f1nance.agent`. The profile was retired on
  2026-08-16 (removed; backup at
  `~/.hermes/archive/f1nance-profile-retired-2026-08-16.tar.gz`) — F1NANCE is
  now fully standalone.
- Exit criteria met: zero Hermes-only coupling in the native core (only
  docstring mentions — no imports), all six capability domains running on the
  standalone substrate, and 329 offline tests green on both.

## Phase 7 — Fixed income ✅

- `f1nance/fixed_income/` engine, stdlib-only (no numpy, no Hermes):
  - `curves` — discount factors, spot/forward rates, present value (flat +
    interpolated curve), and par→spot bootstrapping (annual-coupon par bonds
    at consecutive integer tenors). Inverted curves are reported, not
    "fixed"; interpolation raises outside the curve rather than extrapolating.
  - `bonds` — clean-price bond pricing, yield-to-maturity (bisection),
    Macaulay/modified duration, convexity, DV01 — closed-form, no
    finite-difference approximation.
- Every metric raises on degenerate input (a rate that implies a non-positive
  discount factor, non-increasing tenors, non-integer period counts,
  non-positive price, out-of-range interpolation) rather than fabricating.
- `fixed-income` skill (v0.1.0) fronting the engine; the standalone agent
  gained four fixed-income tools (`fixedincome_price`, `fixedincome_ytm`,
  `fixedincome_risk`, `fixedincome_curve`) — 22 tools total.
- 41 offline unit tests added (370 total, all green); `price`/`ytm`/
  `duration`/`pv`/`pv_curve`/`forward`/`bootstrap` CLI with JSON output.

## Phase 8 — Derivatives ✅

- `f1nance/derivatives/` engine, stdlib-only (no numpy, no scipy, no Hermes):
  - `black_scholes` — closed-form European pricing (Black-Scholes), the
    normal CDF/PDF over `math.erf`, closed-form Greeks (delta/gamma/vega/
    theta/rho — no finite difference), and an implied-volatility solver
    (bisection) that **raises on a price outside the model's no-arbitrage
    bounds** (below intrinsic or above the deep-in-the-money limit) rather
    than fabricating a vol.
  - `binomial` — a Cox-Ross-Rubinstein lattice for European and American
    options (early-exercise premium), the honest fallback for payoffs
    Black-Scholes cannot price closed-form. Raises when the risk-neutral
    probability leaves `[0, 1]`.
  - Reuses the continuous-compounding convention from Phase 7 (rates and
    vol are annualized decimal; time is years).
- Every metric raises on degenerate input (non-positive spot/strike/time/
  volatility, `steps < 1`, a price outside the no-arbitrage bounds) rather
  than fabricating.
- `derivatives` skill (v0.1.0) fronting the engine; the standalone agent
  gained four derivatives tools (`derivatives_price`, `derivatives_greeks`,
  `derivatives_implied_vol`, `derivatives_binomial`) — 26 tools total.
- 34 offline unit tests added (404 total, all green); `price`/`greeks`/
  `implied_vol`/`binomial` CLI with JSON output.

## Phase 9 — Risk management ✅

- `f1nance/risk_management/` engine, stdlib-only (no numpy, no Hermes):
  - `limits` — named risk limits (max/min thresholds) checked against current
    metrics, with breach / headroom / utilization reported. A limit that
    references a metric the caller did not supply **raises** rather than
    fabricating a pass — a missing number is a limit not checked.
  - `stress` — scenario stress testing (linear factor shocks → P&L per
    scenario, with the worst contributor named) and reverse stress testing
    (solve the single-factor shock that produces a target loss, signed
    correctly for long vs short exposure).
  - `backtest` — VaR backtesting: the Kupiec proportion-of-failures test and
    Christoffersen independence / conditional-coverage tests, each a
    likelihood ratio with a chi-square p-value. An exception is
    `realized < -var_forecast` (VaR is a positive loss, returns are signed).
- This is the layer that makes the "risk first" guardrail a *checkable
  contract* on top of Phase-2 `portfolio/risk` (the VaR/CVaR/vol/drawdown
  numbers) and Phase-8 Greeks (gamma/vega exposure).
- Every metric raises on degenerate input (a limit referencing a missing
  metric, an empty exposure map, a scenario that shocks nothing, a negative
  VaR forecast, misaligned series) rather than fabricating.
- `risk-management` skill (v0.1.0) fronting the engine; the standalone agent
  gained four risk-management tools (`riskmanagement_limits`,
  `riskmanagement_stress`, `riskmanagement_reverse_stress`,
  `riskmanagement_var_backtest`) — 30 tools total.
- 29 offline unit tests added (438 total, all green); `limits`/`stress`/
  `reverse_stress`/`var_backtest` CLI with JSON output.

## Phase 10 — M&A ✅

- `f1nance/m_and_a/` engine, stdlib-only (no numpy, no Hermes): the
  deal-mechanics layer that sits on top of the valuation skill (DCF, comps,
  precedent transactions) — once a target is valued, this prices the *deal*:
  - `accretion_dilution` — the EPS bridge across a cash/stock merger:
    pro-forma net income (standalone NIs + tax-affected synergies −
    tax-affected financing cost) over pro-forma shares, reported as absolute
    ($/share) and relative (%) accretion. A deal whose cash + stock does not
    sum to the purchase price **raises** rather than fabricating a bridge.
  - `synergies` — present-value the run-rate synergies (ramped linearly to
    full run-rate, then grown in perpetuity at ``r > g``), net of one-time
    integration costs and the premium paid; plus the break-even run-rate that
    exactly covers the premium.
  - `lbo` — a leveraged buyout: sources & uses (equity check is the balancing
    plug), a year-by-year debt schedule (FCF repays debt; debt floored at zero
    with excess as cash build), the exit, and the sponsor's MOIC/IRR
    (closed-form — all FCF repays debt, no interim distributions).
- Every metric raises on degenerate input (an unbalanced consideration split,
  a non-positive acquirer share count, ``r <= g``, a non-positive equity check
  from an over-levered capitalization, a tax rate outside ``[0, 1)``) rather
  than fabricating.
- `m-and-a` skill (v0.1.0) fronting the engine; the standalone agent gained
  four M&A tools (`manda_accretion`, `manda_synergies`, `manda_breakeven`,
  `manda_lbo`) — 34 tools total.
- 28 offline unit tests added (471 total, all green); `accretion`/`synergies`/
  `breakeven`/`lbo` CLI with JSON output.

## Phase 11 — Deal memo (integration) ✅

- `f1nance/deal_memo/` engine, stdlib-only (no numpy, no Hermes): the
  integration layer that chains **valuation inputs → M&A → risk** into one
  scored `DealMemo`. `build_deal_memo(spec)` runs accretion/dilution, synergy
  value + break-even, an optional LBO, and the risk limits + scenario stress,
  then derives a `favorable` / `adverse` / `inconclusive` recommendation as a
  pure function of the scorecard — never hand-waved, never fabricated.
- The scorecard gates, derived from the numbers: **accretion** (pass if
  accretive), **synergy coverage** (pass if net synergy value covers premium +
  integration costs), **sponsor return** (pass if LBO IRR meets `hurdle_irr`),
  **risk limits** (pass if no breach), **stress budget** (pass if the worst
  scenario P&L stays within `loss_budget`). A section that cannot be computed
  is recorded in `not_computed` with the reason; an in-scope `skip` (an LBO
  without a hurdle, a stress test without a budget) degrades the verdict to
  `inconclusive` rather than pretending the check passed.
- `deal-memo` skill (v0.1.0) fronting the engine; the standalone agent gained
  one tool (`dealmemo_run`) — 35 tools total.
- 25 offline unit tests added (496 total, all green); `memo` CLI with JSON
  output.

## Principles that survive every phase

- Honesty over confidence. Risk over return. Verified over elegant.
- The repo is the body; the Hermes profile was a temporary projection,
  discarded on the way out (retired 2026-08-16).
- Every phase ships with tests and a clean commit, or it does not ship.
