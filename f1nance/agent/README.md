# F1NANCE Agent — the standalone runtime

The Phase-6 runtime: F1NANCE as its own agent, no Hermes. This package turns
the six capability engines (data, portfolio, quant, execution, desk, core)
into a single tool-calling agent that runs on its own substrate — its own
entry point, its own tool registry, its own memory/decision store.

Hermes-independent by design: standard library only (``urllib`` for the model
call, ``dataclasses``/``json`` for everything else), no Hermes imports, no
numpy/pandas. Runs on any Python 3.9+; the model substrate is DeepSeek-v4-pro
via the DeepSeek API (the Prime Directive).

## The shape

```
user message
   │
   ▼
system prompt  ── SOUL.md + active store facts + working contract
   │
   ▼
model (DeepSeek-v4-pro, tool-calling)
   │  └─ tool_calls? ──► ToolRegistry.dispatch ──► engine ──► JSON result
   │                                                     (data/portfolio/quant/
   │                                                      execution/desk/core)
   └─ content? ──► the answer
```

The loop is synchronous and bounded: it executes tool calls the model requests
and feeds results back until the model answers, then stops. A failing tool is
returned to the model as ``{"error": ...}`` — the loop never fabricates a
result, and a model that does not settle within ``--max-steps`` turns raises
rather than inventing an answer.

## Modules

| Module | What it does |
|---|---|
| `paths` | Canonical locations for SOUL.md and the provenance store |
| `client` | `AgentClient` — chat completions with tool calling over `urllib`; `ToolCall` parsing; the echo/result message helpers |
| `tools` | `Tool` / `ToolRegistry` and the built-in toolset (18 tools over the six engines + the store) |
| `system` | The system-prompt builder (SOUL + active store facts + working contract) |
| `loop` | `Agent` — the tool-calling conversation loop |

## The toolset

| Group | Tools |
|---|---|
| Market data | `market_price`, `market_macro`, `market_facts`, `market_filings` |
| Portfolio & risk | `portfolio_value`, `portfolio_risk`, `portfolio_attribution` |
| Quant & backtest | `quant_capm`, `quant_ff`, `quant_backtest`, `quant_momentum` |
| Execution & compliance | `execution_order`, `execution_impact`, `execution_ledger` |
| Desk | `desk_run` (five seats, one verdict, live model executor) |
| Provenance store | `memory_record`, `memory_export`, `memory_retract` |

Each tool's JSON schema is the model-facing contract; each handler calls the
engine directly (the data handlers fetch through the cache, so a stale cache
triggers a real fetch, a down source raises honestly).

## Run

```bash
cd "/home/mustbearn/Projects/AI Agents/F1NANCE Agent"

# one-shot
f1nance/.venv/bin/python -m f1nance.agent chat -q "value a 60/40 AAPL/TLT portfolio"

# interactive
f1nance/.venv/bin/python -m f1nance.agent

# introspect (no network, no model)
f1nance/.venv/bin/python -m f1nance.agent --list-tools
f1nance/.venv/bin/python -m f1nance.agent --system
```

Live runs need an API key (``F1NANCE_API_KEY`` or ``DEEPSEEK_API_KEY``); the
agent refuses to guess a credential. ``--list-tools`` and ``--system`` need no
key — they exercise the offline surface.

## Store-first memory

The agent wakes with its durable facts (identity/directive/user/memory/
decision) in the system prompt, read from the provenance store
(`f1nance/core/store.json`). It records new facts and decisions through the
`memory_*` tools, so what it learns survives the session in the body repo, not
in the (discarded) conversation. `--record` additionally appends each completed
exchange as a `decision` fact.

## Test

```bash
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests
```

Offline; the model client is stubbed, the handlers run against the real
engines, and the loop is exercised with a fake client — no network, no model,
no Hermes.
