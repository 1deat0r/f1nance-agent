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
  Phase 6 ✅, Phase 7 ✅, Phase 8 ✅, Phase 9 ✅.** Phase 6 shipped the
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
- **438 offline unit tests** (`f1nance/tests/`; 404 pre-Phase-9 + 29 in
  `test_risk_management.py` + 5 risk-management tool tests in
  `test_agent.py`), all green:
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
  upstream `main` (`d5773bfc3`) on 2026-08-16** — all SHAs below are the
  post-rebase values; new `main` head is `c390d4713` (Phase 7):
  - `1c66debf8` — `feat(f1nance): found the sovereign financial-agent harness`
  - `d4ce4fe75` — `docs(f1nance): make the end-state explicit — F1NANCE leaves Hermes…`
  - `a0ccaa8c7` — `docs(f1nance): add HANDOFF.md for fresh-session pickup`
  - `4091efdd0` — `feat(f1nance): add Phase-1 data substrate (fetch/cache layer + tests)`
  - `16756293b` — `docs(f1nance): mark Phase 1 complete; refresh skill/roadmap/handoff`
  - `2e32fc8d2` — `docs(f1nance): finalize HANDOFF for fresh-session pickup (Phase 2 ready)`
  - `9e7c699fc` — `feat(f1nance): add Phase-2 portfolio and risk engine`
  - `0bf6c0be8` — `docs(f1nance): record Phase-2 commit hash in HANDOFF`
  - `b404f59a2` — `feat(f1nance): add Phase-3 quant and backtesting engine`
  - `7303d6ad7` — `docs(f1nance): record Phase-3 commit hash and state in HANDOFF`
  - `e8537e449` — `docs(f1nance): complete the HANDOFF commit lineage`
  - `a5017c335` — `feat(f1nance): add Phase-4 execution and compliance layer`
  - `926133e00` — `docs(f1nance): record Phase-4 commit hash and state in HANDOFF`
  - `5b44708db` — `docs(f1nance): note terminal guard workaround in HANDOFF quirks`
  - `a9437995b` — `feat(f1nance): add Phase-5 desk (multi-agent) + store-first core`
  - `4180f3e78` — `docs(f1nance): record Phase-5 commit hash and state in HANDOFF`
  - `265ae0d45` — `feat(f1nance): add desk live executor (Hermes-free model call) + live CLI`
  - `463851fc8` — `docs(f1nance): record desk live executor in HANDOFF`
  - `8ecaef300` — `feat(f1nance): add Phase-6 standalone agent runtime (no Hermes)`
  - `daca6fb96` — `docs(f1nance): record Phase-6 commit hash and state in HANDOFF`
  - `73c92afa9` — `docs(f1nance): record live verification of Phase-6 agent loop in HANDOFF`
  - `11b6d77c1` — `docs(f1nance): record upstream rebase (9c58a78a7) in HANDOFF`
  - `8ff4ae75f` — `docs(f1nance): refresh next steps — profile retirement gated, Phase-7 pointer`
  - `c390d4713` — `feat(f1nance): add Phase-7 fixed-income engine (bonds, yield curves, duration)`
  - `0f24132d4` — `feat(f1nance): add Phase-8 derivatives engine (Black-Scholes, Greeks, binomial)`
  - `359278c61` — `feat(f1nance): add Phase-9 risk-management engine (limits, stress, VaR backtest)`
- Upstream `main` moves fast. Re-check `git ls-remote origin HEAD` before
  claiming "latest". Rebases this session: `9c58a78a7` → `d5773bfc3`
  (2026-08-16); re-rebase when upstream advances again, as a separate step
  from feature work.
- 11 finance skills under `f1nance/skills/`; `market-data`,
  `portfolio-management`, and `quant-methods` at v0.2.0, `execution-trading`,
  `fixed-income`, `derivatives`, and `risk-management` at v0.1.0. The `desk`,
  `core`, `agent`, `fixed_income`, `derivatives`, and `risk_management`
  packages are engines/runtime, not skills.

## Skills (canonical source: `f1nance/skills/`)

`f1nance` (umbrella/harness), `market-data` (v0.2.0 — fronted by the
`f1nance/data` layer), `portfolio-management` (v0.2.0 — backed by the
`f1nance/portfolio` engine), `valuation`,
`financial-statement-analysis`, `macro-analysis`, `quant-methods` (v0.2.0 —
backed by the `f1nance/quant` engine), `execution-trading` (v0.1.0 — backed
by the `f1nance/execution` engine), `fixed-income` (v0.1.0 — backed by the
`f1nance/fixed_income` engine), `derivatives` (v0.1.0 — backed by the
`f1nance/derivatives` engine), `risk-management` (v0.1.0 — backed by the
`f1nance/risk_management` engine). Roadmap
additions: `m-and-a`.

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

1. ✅ **Live-verified the agent loop** (2026-08-16) — see Current state above.
2. ✅ **Re-rebased onto upstream `main`** (`d5773bfc3`) 2026-08-16; `main ==
   fork/main`. **Upstream has advanced again** — `git ls-remote origin HEAD`
   now shows `460d34564` vs our `d5773bfc3`; re-rebase as a separate step
   from feature work, then re-run the suite.
3. ✅ **Phase 7 — fixed income** delivered (2026-08-16): `f1nance/fixed_income/`
   engine + `fixed-income` skill (v0.1.0) + 4 agent tools + 41 tests. 1deat0r
   picked fixed-income as the first roadmap skill.
4. **Retire the Hermes profile** (`~/.hermes/profiles/f1nance/`) when 1deat0r
   confirms the standalone runtime is primary. The profile stays a bootstrap
   fallback until then — do NOT touch it before 1deat0r says so. Back up the
   projected SOUL/skills first if anything exists there that isn't already in
   `f1nance/` (it should all be derived from the repo).
5. ✅ **Phase 8 — derivatives** delivered (2026-08-16): `f1nance/derivatives/`
   engine (Black-Scholes + Greeks + implied vol + binomial lattice) +
   `derivatives` skill (v0.1.0) + 4 agent tools + 34 tests.
6. ✅ **Phase 9 — risk management** delivered (2026-08-16):
   `f1nance/risk_management/` engine (limits + stress + VaR backtesting) +
   `risk-management` skill (v0.1.0) + 4 agent tools + 34 tests. Next roadmap
   pick: **m-and-a** (deal process & structuring; overlaps `valuation`, which
   already owns DCF/comps/precedent transactions — m-and-a adds the deal
   mechanics: accretion/dilution, synergies, LBO). Same pattern: a
   stdlib-only engine in `f1nance/<domain>/` (CLI + JSON output, `raise` on
   degenerate input, never fabricate), a fronting SKILL.md, offline unit
   tests in `f1nance/tests/`, agent tools in `f1nance/agent/tools.py`, and a
   clean commit. Re-project to the profile (step 7) only while it is still in
   use.
7. Re-project repo → profile after editing `f1nance/` skills (see Resume
   commands) — only relevant while the profile is still in use.

## Resume commands

```bash
# standalone agent (Phase 6 — the primary interface now)
cd "/home/mustbearn/Projects/AI Agents/F1NANCE Agent"
f1nance/.venv/bin/python -m f1nance.agent                 # interactive REPL
f1nance/.venv/bin/python -m f1nance.agent chat -q "value NVDA"   # one-shot (needs key)
f1nance/.venv/bin/python -m f1nance.agent --list-tools    # dump 30 tool schemas
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
