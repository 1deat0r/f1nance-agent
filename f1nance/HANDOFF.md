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

**Trajectory (explicit directive from 1deat0r):** F1NANCE becomes its own
standalone agent, **separate from Hermes**. Hermes is the bootstrap chassis,
not the body. See `SOUL.md` → `## Trajectory`, `ARCHITECTURE.md` →
`**End state**`, `ROADMAP.md` → `Phase 6`.

## Where things live

- **Body repo:** `/home/mustbearn/Projects/AI Agents/F1NANCE Agent`
  - `origin` → NousResearch/hermes-agent (upstream; rebase to stay current)
  - `fork` → `1deat0r/f1nance-agent` (**public** on GitHub)
  - native core: `f1nance/` (SOUL, README, ARCHITECTURE, ROADMAP, HANDOFF,
    VERSION, skills/, data/ substrate, tests/)
- **Runtime profile:** `~/.hermes/profiles/f1nance/` (DeepSeek-v4-pro, TUI)
  - `SOUL.md` + `skills/` are a **projection of `f1nance/`** — the repo is
    canonical, the profile is derived
  - `f1nance_body_path` pointer → the repo

## Current state (verified this session)

- **Phase 0 ✅, Phase 1 ✅, Phase 2 ✅, Phase 3 ✅, Phase 4 ✅, Phase 5 ✅.** Phase 1 shipped the `f1nance/data/`
  fetch/cache layer (see `f1nance/data/README.md`): stdlib-first (stooq, FRED,
  EDGAR), yfinance optional in its own `f1nance/.venv/` (Python 3.11),
  as-of/source/degraded provenance on every result, graceful degradation, no
  fabrication. Phase 2 shipped the `f1nance/portfolio/` engine (see
  `f1nance/portfolio/README.md`): stdlib-only positions (weights, exposure,
  FX, cash drag, rebalance), risk (vol, Sharpe/Sortino, VaR/CVaR, beta,
  drawdown, concentration), and Brinson-Fachler attribution. Phase 3 shipped
  the `f1nance/quant/` engine (see `f1nance/quant/README.md`): stdlib-only
  OLS/ridge regression, CAPM and multi-factor exposure models, cross-sectional
  factor construction, and a walk-forward backtesting harness with explicit
  costs, structural look-ahead guards, and honest in-sample/out-of-sample
  reporting. Phase 4 shipped the `f1nance/execution/` engine (see
  `f1nance/execution/README.md`): stdlib-only orders (market/limit/stop/
  stop-limit, with validation plus marketability and stop-side assessment),
  slippage & market impact (half-spread + square-root impact + fees), and an
  append-only compliance trade log that mirrors every decision with its
  rationale, confidence, and loss case — rejections recorded, never dropped.
  Phase 5 shipped the `f1nance/desk/` engine (see `f1nance/desk/README.md`):
  stdlib-only multi-agent coordination — a five-seat roster (PM, trader,
  quant, banker, CFO) over the six capability domains, deterministic routing,
  and an executor-injected coordinator that folds each seat's thesis + stance
  + confidence + loss case into one verdict (dissent surfaced, every loss
  case preserved). And the `f1nance/core/` engine (see
  `f1nance/core/README.md`): an append-only provenance-aware memory/decision
  store (supersede/retract, never overwrite) with a projector that renders
  the active facts into a derived view — the repo is the body, the profile is
  the projection.
- **Desk live executor wired** (`f1nance/desk/live.py`): the `Executor` seam
  is now backed by a Hermes-free model call (`ModelClient` over stdlib
  `urllib`, DeepSeek by default) — `build_prompt` / `parse_finding` /
  `model_executor` / `env_client` — with a `live` CLI command and a
  bounded-retry parser that raises rather than fabricates a finding.
  Live-verified against the real DeepSeek endpoint (two-seat trim brief →
  `neutral` @ 0.7; no-fabrication guardrail visibly respected in the output).
- **287 offline unit tests** (`f1nance/tests/`; 29 Phase-1 + 62 Phase-2 + 49
  Phase-3 + 64 Phase-4 + 58 Phase-5 + 25 desk-live), all green:
  `f1nance/.venv/bin/python -m unittest discover -s f1nance/tests`.
- **Live-verified** against yfinance (AAPL), FRED (CPIAUCSL), and SEC EDGAR
  (Apple CIK 320193 → 505 XBRL tags). Cache hit / as-of / degraded confirmed.
- F1NANCE commits on `main` (pushed; `main == fork/main`):
  - `bc552421a` — `feat(f1nance): found the sovereign financial-agent harness`
  - `4b6ab5345` — `docs(f1nance): make the end-state explicit — F1NANCE leaves Hermes…`
  - `1d3021d7f` — `docs(f1nance): add HANDOFF.md for fresh-session pickup`
  - `a30c999e5` — `feat(f1nance): add Phase-1 data substrate (fetch/cache layer + tests)`
  - `f66e24852` — `docs(f1nance): mark Phase 1 complete; refresh skill/roadmap/handoff`
  - `ce501ceb3` — `docs(f1nance): finalize HANDOFF for fresh-session pickup (Phase 2 ready)`
  - `660587344` — `feat(f1nance): add Phase-2 portfolio and risk engine`
  - `5238eed9a` — `docs(f1nance): record Phase-2 commit hash in HANDOFF`
  - `108e1573b` — `feat(f1nance): add Phase-3 quant and backtesting engine`
  - `2de11389b` — `docs(f1nance): record Phase-3 commit hash and state in HANDOFF`
  - `119220e2b` — `feat(f1nance): add Phase-4 execution and compliance layer`
  - `4638fba7e` — `feat(f1nance): add Phase-5 desk (multi-agent) + store-first core`
  - `7f9fe4c3e` — `feat(f1nance): add desk live executor (Hermes-free model call) + live CLI`
- Upstream `main` moves fast (it advanced repeatedly during this session).
  Re-check `git ls-remote origin HEAD` before claiming "latest". **Not yet
  rebased** — commit Phase work first, then rebase as a separate step.
- 8 finance skills under `f1nance/skills/`; `market-data`,
  `portfolio-management`, and `quant-methods` at v0.2.0, `execution-trading`
  new at v0.1.0. No new skill in Phase 5 — `desk` and `core` are engines.

## Skills (canonical source: `f1nance/skills/`)

`f1nance` (umbrella/harness), `market-data` (v0.2.0 — fronted by the
`f1nance/data` layer), `portfolio-management` (v0.2.0 — backed by the
`f1nance/portfolio` engine), `valuation`,
`financial-statement-analysis`, `macro-analysis`, `quant-methods` (v0.2.0 —
backed by the `f1nance/quant` engine), `execution-trading` (v0.1.0 — backed
by the `f1nance/execution` engine). Roadmap
additions: `m-and-a`, `fixed-income`, `derivatives`, `risk-management`.

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
  Workaround: `git add -A`, then a single-line `git commit -m "..."` — that
  runs clean.
- **deepseek-v4-pro is a reasoning model** — it spends `max_tokens` on
  `reasoning_content` *before* `content`, so a small cap truncates the
  chain-of-thought and returns empty content (`finish_reason: length`). The
  desk live executor defaults `max_tokens` to 8192 (override via
  `F1NANCE_MODEL_MAX_TOKENS`); a raw probe with 1000 reproduced the empty
  response.

## Next steps (pick up here)

1. **Phase 6 — independence (leave the chassis)**: F1NANCE becomes its own
   standalone agent — own runtime/entry point, own tool registry, own memory
   and decision substrate (the `f1nance/core/` store is the seed), with no
   Hermes-only coupling in the native core. The desk already runs live (the
   `live` executor is wired); what remains is the standalone runtime itself.
   Exit criteria: all finance capabilities run on the standalone substrate
   and tests are green on both.
2. Optionally rebase upstream (`git fetch origin && git rebase origin/main`)
   as a separate step from feature work.
3. Re-project repo → profile after editing `f1nance/` skills (see Resume
   commands) so any skill edits are live in the runtime.

## Resume commands

```bash
hermes -p f1nance                        # interactive
hermes -p f1nance chat -q "value NVDA"   # one-shot

# data substrate
cd "/home/mustbearn/Projects/AI Agents/F1NANCE Agent"
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
