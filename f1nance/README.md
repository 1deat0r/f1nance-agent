# F1NANCE Agent

A sovereign financial-agent harness, hard-forked from
[Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research) at
a pinned upstream commit.

F1NANCE Agent is one agent that wears every hat in finance — Financial
Advisor, Accountant, Investment Advisor, Hedge Fund Manager, Portfolio
Manager, Macro & Equities Sales & Trading, M&A Director, Investment Banking
Director, Senior Banker, Quantitative Analyst, and Chief Financial Officer. It
is not a bundle of prompts; it is a harness that routes a task to the right
discipline, gathers real market data, analyzes it with real methodology, and
delivers a thesis with a confidence level and the specific risks that would
make it wrong.

Its Operator is **1deat0r** (also: **The 1deat0r**). F1NANCE refers to its
Operator only by those names.

## What this repo is

This is a **hardfork**, not a wrapper:

- `origin` tracks upstream `NousResearch/hermes-agent` (rebased to stay current).
- `fork` is `1deat0r/f1nance-agent` — the diverging lineage.
- `f1nance/` is F1NANCE's **native core**: identity, harness architecture,
  skills, roadmap, and — since Phase 6 — the standalone runtime
  (`f1nance/agent/`). This directory is the agent, distinct from the Hermes
  runtime it bootstrapped on.
- The Hermes runtime (`~/.hermes/hermes-agent`) is the bootstrap chassis.
  F1NANCE ran as a Hermes **profile** (`~/.hermes/profiles/f1nance/`) whose
  `SOUL.md` and skills are projections of this repo's `f1nance/` directory;
  since Phase 6 the body runs on its own (`python -m f1nance.agent`).

## Layout

```
f1nance/
├── SOUL.md           # the identity — what F1NANCE is, its law, its beliefs
├── README.md         # this file
├── ARCHITECTURE.md   # the harness: role taxonomy → capabilities → tools → guardrails
├── ROADMAP.md        # phased build plan
├── HANDOFF.md        # session-state — read first on wake, then verify against git
├── VERSION           # 0.07
├── __init__.py       # native core package root
├── data/             # Phase-1 fetch/cache layer (stdlib-first; yfinance optional)
├── portfolio/        # Phase-2 portfolio & risk engine (stdlib-only)
├── quant/            # Phase-3 quant & backtesting engine (stdlib-only)
├── execution/        # Phase-4 execution & compliance layer (stdlib-only)
├── desk/             # Phase-5 multi-agent coordination layer (stdlib-only)
├── core/             # Phase-5 store-first evolution loop (stdlib-only)
├── agent/            # Phase-6 standalone runtime (entry point, tools, memory)
├── fixed_income/     # Phase-7 fixed-income engine (stdlib-only)
├── tests/            # offline unit tests (unittest; no Hermes, no network)
└── skills/           # canonical finance skills (SKILL.md each), installed into the profile
    ├── f1nance/                        # umbrella: the harness operating manual
    ├── market-data/                    # where and how to get real market data
    ├── valuation/                      # DCF, comps, precedent transactions
    ├── portfolio-management/           # allocation, risk, rebalancing, attribution
    ├── financial-statement-analysis/   # the accountant/CFO lens on the 3 statements
    ├── macro-analysis/                 # rates, FX, credit, inflation, central banks
    ├── quant-methods/                  # factors, stats, backtesting discipline
    ├── execution-trading/              # orders, execution costs, the trade log
    └── fixed-income/                   # bond pricing, yield curves, duration
```

## Quick start

The runtime profile is created and kept in sync from this repo:

```bash
# 1. (one-time) create the profile and install the identity + skills
hermes profile create f1nance --description "Sovereign financial-agent harness"
cp f1nance/SOUL.md ~/.hermes/profiles/f1nance/SOUL.md
cp -r f1nance/skills/* ~/.hermes/profiles/f1nance/skills/

# 2. run it
hermes --profile f1nance          # interactive
hermes --profile f1nance chat -q "…"   # one-shot
```

## Standalone (no Hermes) — Phase 6

The body runs on its own substrate — no Hermes, stdlib-only:

```bash
cd "/home/mustbearn/Projects/AI Agents/F1NANCE Agent"

# one-shot
f1nance/.venv/bin/python -m f1nance.agent chat -q "value a 60/40 AAPL/TLT portfolio"

# interactive REPL
f1nance/.venv/bin/python -m f1nance.agent

# introspect (offline)
f1nance/.venv/bin/python -m f1nance.agent --list-tools
f1nance/.venv/bin/python -m f1nance.agent --system
```

Live runs need `F1NANCE_API_KEY` (or `DEEPSEEK_API_KEY`) in the environment.
See `f1nance/agent/README.md`.

## Staying current with upstream

```bash
git fetch origin
git rebase origin/main            # keep the hardfork current
```

## License

The upstream chassis is MIT (Nous Research). F1NANCE's native core in
`f1nance/` is F1NANCE's own. See the upstream `LICENSE` for the inherited
code.
