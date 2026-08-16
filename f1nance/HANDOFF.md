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
  Phase 6 ✅.** Phase 6 shipped the `f1nance/agent/` standalone runtime (see
  `f1nance/agent/README.md`): stdlib-only, no Hermes imports —
  - `client` — `AgentClient`, an OpenAI-compatible chat-completions client
    with tool calling over stdlib `urllib` (reuses the desk's `ModelError`
    and DeepSeek defaults; strips `reasoning_content` on echo-back).
  - `tools` — `Tool`/`ToolRegistry` + 18 engine-backed tools over the six
    domains plus the provenance store; a failing tool returns an honest
    `{"error": ...}` rather than crashing the loop.
  - `system` — the system-prompt builder (SOUL + active store facts + the
    working contract).
  - `loop` — the `Agent` tool-calling loop, bounded by a step cap that raises
    rather than inventing.
  - `__main__` — entry point: interactive REPL, `chat -q "…"`, `--list-tools`,
    `--system`.
- **329 offline unit tests** (`f1nance/tests/`; 287 pre-Phase-6 + 42 new in
  `test_agent.py`), all green:
  `f1nance/.venv/bin/python -m unittest discover -s f1nance/tests`.
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
  - `f384ebca2` — `feat(f1nance): add Phase-6 standalone agent runtime (no Hermes)`
- Upstream `main` moves fast. Re-check `git ls-remote origin HEAD` before
  claiming "latest". **Not yet rebased** — commit Phase work first, then rebase
  as a separate step.
- 8 finance skills under `f1nance/skills/`; `market-data`,
  `portfolio-management`, and `quant-methods` at v0.2.0, `execution-trading`
  at v0.1.0. The `desk`, `core`, and `agent` packages are engines/runtime, not
  skills.

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

1. **Live-verify the agent loop** ✅ done (2026-08-16): no-tool call, a pure
   tool call (`portfolio_value`), and a network tool call (`market_price`) all
   verified live against the real DeepSeek endpoint — the `tool_calls` wire
   shape matches `parse_tool_calls`. See Current state above.
2. **Retire the Hermes profile** when 1deat0r confirms the standalone runtime
   is primary — the profile stays as a bootstrap fallback until then.
3. Optionally rebase upstream (`git fetch origin && git rebase origin/main`)
   as a separate step from feature work.
4. Re-project repo → profile after editing `f1nance/` skills (see Resume
   commands) — only relevant while the profile is still in use.

## Resume commands

```bash
# standalone agent (Phase 6 — the primary interface now)
cd "/home/mustbearn/Projects/AI Agents/F1NANCE Agent"
f1nance/.venv/bin/python -m f1nance.agent                 # interactive REPL
f1nance/.venv/bin/python -m f1nance.agent chat -q "value NVDA"   # one-shot (needs key)
f1nance/.venv/bin/python -m f1nance.agent --list-tools    # dump 18 tool schemas
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
