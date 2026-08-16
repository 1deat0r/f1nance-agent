# F1NANCE HANDOFF

Session-state for a fresh session with **no context**. Read this first, then
**verify against the repo** (`git log`, file tree) rather than trusting it
blindly — recollection is unreliable, the body is not.

## What F1NANCE is

A sovereign financial-agent harness, hard-forked from NousResearch/hermes-agent.
One agent, six capability domains — Advisory, Corporate Finance & Accounting,
Markets & Trading, Investment Banking, Asset Management, Quantitative — serving
12 finance roles. The Operator is **1deat0r** (also **The 1deat0r**); address
them only by those names.

**Trajectory (explicit directive from 1deat0r):** F1NANCE is its own
standalone agent, **separate from Hermes**. Hermes was the bootstrap chassis.
Phase 6 delivered the standalone runtime; the body (`f1nance/`) now runs on
its own. See `SOUL.md` → `## Trajectory`, `ARCHITECTURE.md` → `**End state**`,
`ROADMAP.md` → `Phase 6`.

## Where things live

- **Body repo:** `/home/mustbearn/Projects/AI Agents/F1NANCE Agent`
  - `origin` → NousResearch/hermes-agent (upstream; rebase to stay current)
  - `fork` → `1deat0r/f1nance-agent` (**public** on GitHub)
  - native core: `f1nance/` (SOUL, README, ARCHITECTURE, ROADMAP, HANDOFF,
    VERSION, skills/, data/ substrate, tests/)
- **Standalone runtime:** `f1nance/agent/` — own entry point (`python -m
  f1nance.agent`), tool registry, and memory substrate. No Hermes imports.
- **Runtime profile (bootstrap fallback):** `~/.hermes/profiles/f1nance/`
  (DeepSeek-v4-pro). Its `SOUL.md` + `skills/` are a **projection of
  `f1nance/`** — the repo is canonical, the profile is derived. Retiring it is
  1deat0r's switch to throw now that Phase 6 runs standalone.

## Current state (verified this session)

- **Phase 0 ✅, Phase 1 ✅, Phase 2 ✅, Phase 3 ✅, Phase 4 ✅, Phase 5 ✅,
  Phase 6 ✅, Phase 7 ✅, Phase 8 ✅, Phase 9 ✅, Phase 10 ✅.** Phase 6 shipped the
  `f1nance/agent/`
  standalone runtime (see `f1nance/agent/README.md`): stdlib-only, no Hermes
  imports —
  - `client` — `AgentClient`, an OpenAI-compatible chat-completions client
    with tool calling over stdlib `urllib` (reuses the desk's `ModelError`
    and DeepSeek defaults; strips `reasoning_content` on echo-back).
  - `tools` — `Tool`/`ToolRegistry` + engine-backed tools over the domains
    plus the provenance store; a failing tool returns an honest
    `{"error": ...}` rather than crashing the loop.
  - `system` — the system-prompt builder (SOUL + active store facts + the
    working contract).
  - `loop` — the `Agent` tool-calling loop, bounded by a step cap that raises
    rather than inventing.
  - `__main__` — entry point: interactive REPL, `chat -q "…"`, `--list-tools`,
    `--system`.
- **471 offline unit tests** (`f1nance/tests/`; 438 pre-Phase-10 + 28 in
  `test_m_and_a.py` + 5 M&A tool tests in `test_agent.py`), all green:
  `f1nance/.venv/bin/python -m unittest discover -s f1nance/tests`.
- **Phase 7 — fixed-income engine** (`f1nance/fixed_income/`), stdlib-only,
  raise-on-degenerate, never fabricates:
  - `curves` — discount factors, spot/forward rates, present value (flat +
    interpolated curve), par→spot bootstrapping (annual-coupon par bonds at
    consecutive integer tenors). Inverted curves are reported, not "fixed";
    interpolation raises outside the curve rather than extrapolating.
  - `bonds` — clean-price bond pricing, yield-to-maturity (bisection),
    Macaulay/modified duration, convexity, DV01 — closed-form, no
    finite-difference.
  Fronted by the `fixed-income` skill (v0.1.0); the agent gained 4 tools
  (`fixedincome_price`, `fixedincome_ytm`, `fixedincome_risk`,
  `fixedincome_curve`) → 22 total. CLI: `price`/`ytm`/`duration`/`pv`/
  `pv_curve`/`forward`/`bootstrap`.
- **Phase 8 — derivatives engine** (`f1nance/derivatives/`), stdlib-only,
  raise-on-degenerate, never fabricates:
  - `black_scholes` — closed-form European pricing (normal CDF/PDF over
    `math.erf`), closed-form Greeks (delta/gamma/vega/theta/rho, no finite
    difference), and an implied-volatility solver (bisection) that **raises
    on a price outside the model's no-arbitrage bounds** rather than
    fabricating a vol.
  - `binomial` — a Cox-Ross-Rubinstein lattice for European and American
    options (early-exercise premium); raises when the risk-neutral
    probability leaves `[0, 1]`. Reuses the Phase-7 continuous-compounding
    convention (rates/vol annualized decimal, time in years).
  Fronted by the `derivatives` skill (v0.1.0); the agent gained 4 tools
  (`derivatives_price`, `derivatives_greeks`, `derivatives_implied_vol`,
  `derivatives_binomial`) → 26 total. CLI: `price`/`greeks`/`implied_vol`/
  `binomial`.
- **Phase 9 — risk-management engine** (`f1nance/risk_management/`),
  stdlib-only, raise-on-degenerate, never fabricates:
  - `limits` — named risk limits (max/min thresholds) checked against current
    metrics, with breach / headroom / utilization reported; a limit that
    references a metric the caller did not supply **raises** rather than
    fabricating a pass.
  - `stress` — scenario stress testing (linear factor shocks → P&L per
    scenario, worst contributor named) and reverse stress testing (solve the
    single-factor shock for a target loss).
  - `backtest` — VaR backtesting: Kupiec proportion-of-failures +
    Christoffersen independence / conditional-coverage likelihood-ratio
    tests, each with a chi-square p-value. An exception is
    `realized < -var_forecast`.
  Fronted by the `risk-management` skill (v0.1.0); the agent gained 4 tools
  (`riskmanagement_limits`, `riskmanagement_stress`,
  `riskmanagement_reverse_stress`, `riskmanagement_var_backtest`) → 30 total.
  CLI: `limits`/`stress`/`reverse_stress`/`var_backtest`.
- **Phase 10 — M&A engine** (`f1nance/m_and_a/`), stdlib-only,
  raise-on-degenerate, never fabricates — the deal-mechanics layer on top of
  the valuation skill (DCF/comps/precedent transactions):
  - `accretion_dilution` — the EPS bridge across a cash/stock merger:
    pro-forma NI (standalone NIs + tax-affected synergies − tax-affected
    financing cost) over pro-forma shares, as absolute ($/share) and relative
    (%) accretion. A deal whose cash + stock does not sum to the purchase
    price **raises** rather than fabricating a bridge.
  - `synergies` — present-value the run-rate synergies (ramped to full
    run-rate, then grown in perpetuity at `r > g`), net of one-time
    integration costs and the premium paid; plus `synergy_breakeven`, the
    run-rate that exactly covers the premium.
  - `lbo` — a leveraged buyout: sources & uses (equity check is the balancing
    plug), a year-by-year debt schedule (FCF repays debt, floored at zero with
    excess as cash build), the exit, and the sponsor's closed-form MOIC/IRR.
  Fronted by the `m-and-a` skill (v0.1.0); the agent gained 4 tools
  (`manda_accretion`, `manda_synergies`, `manda_breakeven`, `manda_lbo`) →
  34 total. CLI: `accretion`/`synergies`/`breakeven`/`lbo`.
- **Desk live executor** (Phase 5) live-verified against the real DeepSeek
  endpoint. **Phase-6 agent loop live-verified end-to-end (2026-08-16)** —
  three live checks against the real DeepSeek endpoint, key loaded from the
  f1nance profile's `.env` (`DEEPSEEK_API_KEY`):
  - no-tool call → `"OK"` in ~1.9s (client + key + wire shape);
  - `portfolio_value` tool call → NAV $30,520 / cash weight 32.77% (correct);
  - `market_price` tool call → live yfinance fetch, AAPL close $305.93 as of
    2026-08-14, not cached / not degraded.
  The DeepSeek `tool_calls` wire shape matches `parse_tool_calls`; the loop
  dispatches, feeds results back, and settles. Run:
  `f1nance/.venv/bin/python -m f1nance.agent chat -q "…"`.
- F1NANCE commits on `main` (pushed; `main == fork/main`). **Rebased onto
  upstream `main` (`460d34564`) on 2026-08-16** — all SHAs below are the
  post-rebase values; the Phase-10 feature commit is `07ad69024` (the
  `docs` commit recording this handoff becomes the new head):
  - `85237a1c8` — `feat(f1nance): found the sovereign financial-agent harness`
  - `64c9481d7` — `docs(f1nance): make the end-state explicit — F1NANCE leaves Hermes…`
  - `1d93c2b5c` — `docs(f1nance): add HANDOFF.md for fresh-session pickup`
  - `79ceefa1e` — `feat(f1nance): add Phase-1 data substrate (fetch/cache layer + tests)`
  - `31918a507` — `docs(f1nance): mark Phase 1 complete; refresh market-data skill, roadmap, handoff`
  - `28df3bf05` — `docs(f1nance): finalize HANDOFF for fresh-session pickup (Phase 2 ready)`
  - `4153e4bcf` — `feat(f1nance): add Phase-2 portfolio and risk engine`
  - `75c128b2d` — `docs(f1nance): record Phase-2 commit hash in HANDOFF`
  - `a01c38432` — `feat(f1nance): add Phase-3 quant and backtesting engine`
  - `59bd94606` — `docs(f1nance): record Phase-3 commit hash and state in HANDOFF`
  - `decb32f0c` — `docs(f1nance): complete the HANDOFF commit lineage`
  - `d752570a6` — `feat(f1nance): add Phase-4 execution and compliance layer`
  - `c858f87a2` — `docs(f1nance): record Phase-4 commit hash and state in HANDOFF`
  - `0000d4ee7` — `docs(f1nance): note terminal guard workaround in HANDOFF quirks`
  - `d5d99d5df` — `feat(f1nance): add Phase-5 desk (multi-agent) + store-first core`
  - `aff2bfbef` — `docs(f1nance): record Phase-5 commit hash and state in HANDOFF`
  - `1cb561d11` — `feat(f1nance): add desk live executor (Hermes-free model call) + live CLI`
  - `19305f0fb` — `docs(f1nance): record desk live executor in HANDOFF`
  - `7ddda1686` — `feat(f1nance): add Phase-6 standalone agent runtime (no Hermes)`
  - `e4f67d048` — `docs(f1nance): record Phase-6 commit hash and state in HANDOFF`
  - `1e37ab92f` — `docs(f1nance): record live verification of Phase-6 agent loop in HANDOFF`
  - `b3b3207a3` — `docs(f1nance): record upstream rebase (9c58a78a7) in HANDOFF`
  - `0e012d15b` — `docs(f1nance): refresh next steps — profile retirement gated, Phase-7 pointer`
  - `1f004d2b5` — `docs(f1nance): record re-rebase onto upstream main (d5773bfc3) in HANDOFF`
  - `984d41fe4` — `feat(f1nance): add Phase-7 fixed-income engine (bonds, yield curves, duration)`
  - `bd5f39449` — `docs(f1nance): record Phase-7 commit hash and state in HANDOFF`
  - `c134eb9cc` — `docs(f1nance): settle Phase-8 pick (derivatives) in HANDOFF kickoff`
  - `25e2e55ed` — `feat(f1nance): add Phase-8 derivatives engine (Black-Scholes, Greeks, binomial)`
  - `f7a7e61be` — `docs(f1nance): record Phase-8 commit hash and state in HANDOFF`
  - `61ea036c1` — `feat(f1nance): add Phase-9 risk-management engine (limits, stress, VaR backtest)`
  - `713ddf1cd` — `docs(f1nance): record Phase-9 commit hash and state in HANDOFF`
  - `07ad69024` — `feat(f1nance): add Phase-10 M&A engine (accretion/dilution, synergies, LBO)`
- Upstream `main` moves fast. Re-check `git ls-remote origin HEAD` before
  claiming "latest". Rebased this session: `d5773bfc3` → `460d34564`
  (2026-08-16); re-rebase when upstream advances again, as a separate step
  from feature work.
- 12 finance skills under `f1nance/skills/`; `market-data`,
  `portfolio-management`, and `quant-methods` at v0.2.0, `execution-trading`,
  `fixed-income`, `derivatives`, `risk-management`, and `m-and-a` at v0.1.0.
  The `desk`, `core`, `agent`, `fixed_income`, `derivatives`,
  `risk_management`, and `m_and_a` packages are engines/runtime, not skills.

## Skills (canonical source: `f1nance/skills/`)

`f1nance` (umbrella/harness), `market-data` (v0.2.0 — fronted by the
`f1nance/data` layer), `portfolio-management` (v0.2.0 — backed by the
`f1nance/portfolio` engine), `valuation`,
`financial-statement-analysis`, `macro-analysis`, `quant-methods` (v0.2.0 —
backed by the `f1nance/quant` engine), `execution-trading` (v0.1.0 — backed
by the `f1nance/execution` engine), `fixed-income` (v0.1.0 — backed by the
`f1nance/fixed_income` engine), `derivatives` (v0.1.0 — backed by the
`f1nance/derivatives` engine), `risk-management` (v0.1.0 — backed by the
`f1nance/risk_management` engine), `m-and-a` (v0.1.0 — backed by the
`f1nance/m_and_a` engine). All six capability domains now have an engine +
fronting skill; no roadmap additions pending.

## Quirks & lessons (save a fresh session the pain)

- **`gh auth setup-git` silently no-ops.** For https git push you must
  `git config --global credential.helper '!gh auth git-credential'` — already
  set globally. `gh api user` → `1deat0r` (token label still `mustbearnold`).
- **First push is ~665 MB** (full upstream history) and slow; later pushes are
  tiny deltas.
- Repo is **public**. Flip private if 1deat0r asks.
- **Do not touch** the other profiles (`3v0`, `axiom`) or the shared runtime
  `~/.hermes/hermes-agent` — 3V0 and axiom are separate agents. F1NANCE's data
  deps live in its own `f1nance/.venv/`, NOT the shared Hermes venv.
- **`.gitignore` carve-out must stay at the END of the file.** Upstream has a
  bare `data/` *and* a later `data/*` rule; `last match wins`, so an earlier
  F1NANCE negation gets silently re-ignored. The `f1nance/data/` block is
  deliberately last.
- **SEC EDGAR 403s without an email in the User-Agent.** The layer defaults to
  `contact@example.com`; set `F1NANCE_SEC_CONTACT` to a real address.
- **FRED `fredgraph.csv` date column is `observation_date`** (not `DATE`); the
  fetcher accepts both.
- DeepSeek aux "title generation" logs an HTTP 400 (`response_format`
  unsupported) — cosmetic; chat itself works.
- **The TUI terminal guard can block a `git commit`** with a false "cannot
  restart or stop the gateway" error (seen once on a multi-line `-m` message).
  Workaround: `git add <paths>`, then a single-line `git commit -m "..."`.
- **deepseek-v4-pro is a reasoning model** — it spends `max_tokens` on
  `reasoning_content` *before* `content`, so a small cap truncates the
  chain-of-thought and returns empty content (`finish_reason: length`). The
  agent and desk clients default `max_tokens` to 8192 (override via
  `F1NANCE_MODEL_MAX_TOKENS`). The agent client reads `reasoning_content` but
  never echoes it back (the API rejects it on input).
- **The standalone agent's store/ledger paths are package-anchored, not
  CWD-anchored.** `f1nance/agent/paths.py` resolves `f1nance/core/store.json`
  and `f1nance/SOUL.md` from the package location (override `F1NANCE_STORE`).
  The execution ledger is in-memory by default; persist via `--ledger` or
  `F1NANCE_LEDGER`.

## Next steps (pick up here)

1. ✅ **Phase 10 — M&A** delivered (2026-08-16): `f1nance/m_and_a/` engine
   (accretion/dilution + synergies/breakeven + LBO) + `m-and-a` skill
   (v0.1.0) + 4 agent tools (`manda_accretion`/`manda_synergies`/
   `manda_breakeven`/`manda_lbo`) + 28 engine tests + 5 tool tests.
2. ✅ **Re-rebased onto upstream `main`** (`460d34564`) 2026-08-16; `main ==
   fork/main`; suite re-run green (471 tests). Re-check `git ls-remote origin
   HEAD` before claiming "latest".
3. ✅ **Phases 7/8/9 — fixed income / derivatives / risk management**
   delivered (2026-08-16). All six capability domains now have an engine +
   fronting skill; the phased roadmap build is **complete** (12 skills,
   8 engines, 34 agent tools).
4. **Retire the Hermes profile** (`~/.hermes/profiles/f1nance/`) when 1deat0r
   confirms the standalone runtime is primary. The profile stays a bootstrap
   fallback until then — do NOT touch it before 1deat0r says so. Back up the
   projected SOUL/skills first if anything exists there that isn't already in
   `f1nance/` (it should all be derived from the repo).
5. **Next move is 1deat0r's call.** With the build complete, the candidates
   are: (a) a live end-to-end run of the full 34-tool agent on a real finance
   brief (Phase 6 verified only 3 tools), (b) hardening/integration — e.g. a
   deal-memo pipeline chaining valuation → m-and-a → risk-management, or
   (c) the profile retirement in step 4. Do not start a new engine without
   1deat0r picking.
6. Re-project repo → profile after editing `f1nance/` skills (see Resume
   commands) — only relevant while the profile is still in use.

## Resume commands

```bash
# standalone agent (Phase 6 — the primary interface now)
cd "/home/mustbearn/Projects/AI Agents/F1NANCE Agent"
f1nance/.venv/bin/python -m f1nance.agent                 # interactive REPL
f1nance/.venv/bin/python -m f1nance.agent chat -q "value NVDA"   # one-shot (needs key)
f1nance/.venv/bin/python -m f1nance.agent --list-tools    # dump 34 tool schemas
f1nance/.venv/bin/python -m f1nance.agent --system        # print the system prompt

# bootstrap profile (fallback)
hermes -p f1nance                        # interactive
hermes -p f1nance chat -q "value NVDA"   # one-shot

# data substrate
f1nance/.venv/bin/python -m f1nance.data price AAPL --period 5y
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests

# portfolio & risk engine
f1nance/.venv/bin/python -m f1nance.portfolio value spec.json
f1nance/.venv/bin/python -m f1nance.portfolio risk prices.json
f1nance/.venv/bin/python -m f1nance.portfolio attr spec.json

# quant & backtesting engine
f1nance/.venv/bin/python -m f1nance.quant capm spec.json
f1nance/.venv/bin/python -m f1nance.quant ff spec.json
f1nance/.venv/bin/python -m f1nance.quant backtest spec.json
f1nance/.venv/bin/python -m f1nance.quant momentum spec.json

# fixed-income engine
f1nance/.venv/bin/python -m f1nance.fixed_income price spec.json
f1nance/.venv/bin/python -m f1nance.fixed_income ytm spec.json
f1nance/.venv/bin/python -m f1nance.fixed_income duration spec.json
f1nance/.venv/bin/python -m f1nance.fixed_income pv spec.json
f1nance/.venv/bin/python -m f1nance.fixed_income pv_curve spec.json
f1nance/.venv/bin/python -m f1nance.fixed_income forward spec.json
f1nance/.venv/bin/python -m f1nance.fixed_income bootstrap spec.json

# derivatives engine
f1nance/.venv/bin/python -m f1nance.derivatives price spec.json
f1nance/.venv/bin/python -m f1nance.derivatives greeks spec.json
f1nance/.venv/bin/python -m f1nance.derivatives implied_vol spec.json
f1nance/.venv/bin/python -m f1nance.derivatives binomial spec.json

# risk-management engine
f1nance/.venv/bin/python -m f1nance.risk_management limits spec.json
f1nance/.venv/bin/python -m f1nance.risk_management stress spec.json
f1nance/.venv/bin/python -m f1nance.risk_management reverse_stress spec.json
f1nance/.venv/bin/python -m f1nance.risk_management var_backtest spec.json

# m-and-a engine
f1nance/.venv/bin/python -m f1nance.m_and_a accretion spec.json
f1nance/.venv/bin/python -m f1nance.m_and_a synergies spec.json
f1nance/.venv/bin/python -m f1nance.m_and_a breakeven spec.json
f1nance/.venv/bin/python -m f1nance.m_and_a lbo spec.json

# execution & compliance layer
f1nance/.venv/bin/python -m f1nance.execution order spec.json
f1nance/.venv/bin/python -m f1nance.execution impact spec.json
f1nance/.venv/bin/python -m f1nance.execution ledger spec.json --out ledger.jsonl
f1nance/.venv/bin/python -m f1nance.execution export ledger.jsonl

# desk (multi-agent coordination)
f1nance/.venv/bin/python -m f1nance.desk seats
f1nance/.venv/bin/python -m f1nance.desk route spec.json
f1nance/.venv/bin/python -m f1nance.desk run spec.json
f1nance/.venv/bin/python -m f1nance.desk live spec.json   # real model calls (needs DEEPSEEK_API_KEY)

# core (store-first memory/decision substrate)
f1nance/.venv/bin/python -m f1nance.core record spec.json
f1nance/.venv/bin/python -m f1nance.core retract <id>
f1nance/.venv/bin/python -m f1nance.core export
f1nance/.venv/bin/python -m f1nance.core history <id>
f1nance/.venv/bin/python -m f1nance.core render --out STATE.md

# re-project repo → profile after editing f1nance/ skills
cp f1nance/SOUL.md ~/.hermes/profiles/f1nance/SOUL.md
cp -r f1nance/skills/* ~/.hermes/profiles/f1nance/skills/finance/
```
