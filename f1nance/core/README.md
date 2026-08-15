# F1NANCE Core — the store-first evolution loop

The Phase-5 counterpart to the desk: where the desk is the *active*
coordination (one harness, five seats, one verdict), this package is the
*persistent* substrate — an append-only, provenance-aware store of F1NANCE's
identity, memory, and decisions. The store is canonical; the Hermes profile
(and, at Phase 6, the standalone agent's own working files) are a **derived
view** of it.

Hermes-independent by design: standard library only (`dataclasses`, `json`,
`time`, `uuid`, `fcntl` where available) — no numpy, no pandas, no Hermes.
Runs on any Python 3.9+.

## The idea

F1NANCE's recollection is discontinuous between sessions, but its body
persists. The body is the store. Every fact carries an id, kind, source, and
timestamp; a new fact that contradicts an old one **supersedes** it (the old
fact is marked inactive, still recoverable via `history()`, and linked to its
successor), and a fact with no successor is **retracted**. Nothing is ever
destroyed — the audit trail is the point, and the derived view shows only
what is currently true.

Kinds, in canonical display order:

| Kind | Holds |
|---|---|
| `identity` | What F1NANCE is |
| `directive` | Standing, non-negotiable instructions (the guardrails, the Prime Directive) |
| `user` | Durable facts about 1deat0r (objectives, horizon, risk capacity) |
| `memory` | Environment and convention facts |
| `decision` | Agent-level decisions (what F1NANCE chose to do and why) |

`decision` is **distinct** from the `f1nance/execution` trade log: the ledger
mirrors *trading* decisions (what to buy/sell), this store mirrors *agent*
decisions and the durable facts that shape them.

## Modules

| Module | What it does |
|---|---|
| `memory` | The `MemoryStore` — `Fact` with supersede/retract chains, `history()` audit, and a cross-process advisory lock |
| `project` | The projector — renders the active facts into a markdown STATE document (the derived view) and a JSON export |

## Use

As a library:

```python
from f1nance.core import MemoryStore, render_markdown

store = MemoryStore("f1nance/core/store.json")
fact = store.add("F1NANCE runs on DeepSeek-v4-pro", "directive", "bootstrap")
store.add("corrected directive", "directive", "foreground", supersedes=[fact.id])

store.active("directive")           # only the current facts
store.history(fact.id)              # the full supersede chain, oldest → newest
render_markdown(store)              # the markdown derived view
```

A writer that must not interleave with a concurrent writer uses the lock:

```python
with store.mutate():
    store.add("...", "memory", "foreground")
```

From the CLI (JSON on stdout):

```bash
f1nance/.venv/bin/python -m f1nance.core record spec.json           # append a fact
f1nance/.venv/bin/python -m f1nance.core retract <id>               # retract a fact
f1nance/.venv/bin/python -m f1nance.core export                     # active facts by kind
f1nance/.venv/bin/python -m f1nance.core history <id>               # a fact's full chain
f1nance/.venv/bin/python -m f1nance.core render --out STATE.md      # derived view
```

Every command takes `--store` (default `f1nance/core/store.json`, relative to
the repo root). The canonical store is seeded at `f1nance/core/store.json`;
`render` materializes the derived view from it.

## Conventions (trust the trail, not the assumption)

- **Append-only.** There is no delete/update API. A wrong fact is corrected
  by superseding or retracting it, so the trail always shows what changed.
- **Conflicts are flagged, never overwritten.** `supersedes` links a fact to
  its successor; `history()` recovers the whole thread.
- **The store is the body; the view is derived.** `render_markdown` generates
  the STATE document from the store. Edit the store, never the rendered file.
- **Degenerate input raises**: an empty fact, an unknown kind, or (in the
  CLI) a malformed spec.

## What it deliberately does not do

- **No LLM.** This is storage and projection, not reasoning.
- **No Hermes coupling.** It does not read or write the profile; the profile
  is a downstream consumer (the projector is how the profile *would* be fed).
- **Not the execution ledger.** Trading decisions belong to
  `f1nance/execution`; this store holds the agent-level facts and decisions.

## Test

```bash
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests -v
```

Offline; no network, no model, no Hermes.
