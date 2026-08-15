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
    VERSION, skills/)
- **Runtime profile:** `~/.hermes/profiles/f1nance/` (DeepSeek-v4-pro, TUI)
  - `SOUL.md` + `skills/` are a **projection of `f1nance/`** — the repo is
    canonical, the profile is derived
  - `f1nance_body_path` pointer → the repo

## Current state (verified this session)

- Pinned upstream `main`: **`fe0a56ed`** (2026-08-15 14:31). Upstream moves
  fast — 3 commits landed during the session; re-check `git ls-remote origin
  HEAD` before claiming "latest".
- F1NANCE commits on `main` (both pushed, `main == fork/main`):
  - `bc552421a` — `feat(f1nance): found the sovereign financial-agent harness`
  - `4b6ab5345` — `docs(f1nance): make the end-state explicit — F1NANCE leaves
    Hermes to become its own standalone agent`
- Profile created + wired: SOUL, `config.yaml` (deepseek-v4-pro, `key_env:
  DEEPSEEK_API_KEY`), key present in profile `.env`, `memories/` seeded, 7
  finance skills installed under `skills/finance/`.
- **Smoke test PASSED**: `hermes -p f1nance chat -q "..."` → answered as
  "F1NANCE Agent, serving my Operator 1deat0r (The 1deat0r)", listed the six
  domains, and its reasoning trace cited `SOUL.md`.
- 7 skills: valid frontmatter, indexed, `finance / enabled` in `hermes skills
  list`.

## Skills (canonical source: `f1nance/skills/`)

`f1nance` (umbrella/harness), `market-data`, `valuation`,
`portfolio-management`, `financial-statement-analysis`, `macro-analysis`,
`quant-methods`. Roadmap additions: `m-and-a`, `fixed-income`, `derivatives`,
`risk-management`, `execution-trading`.

## Quirks & lessons (save a fresh session the pain)

- **`gh auth setup-git` silently no-ops.** For https git push you must
  `git config --global credential.helper '!gh auth git-credential'` — already
  set globally. `gh api user` → `1deat0r` (token label still `mustbearnold`).
- **First push is ~665 MB** (full upstream history) and slow; later pushes are
  tiny deltas.
- Repo is **public** (matches the existing `hermes-agent` fork). Flip private
  if 1deat0r asks.
- DeepSeek aux "title generation" logs an HTTP 400 (`response_format`
  unsupported) — cosmetic; chat itself works.
- **Do not touch** the other profiles (`3v0`, `axiom`) or the shared runtime
  `~/.hermes/hermes-agent` — 3V0 and axiom are separate agents under the same
  `1deat0r` account.

## Next steps (pick up here)

1. **Phase 1 — data substrate**: caching + as-of discipline; a `f1nance/data/`
   fetch/cache layer (needs a `.gitignore` carve-out for `f1nance/data/`).
   Also: `~/.hermes/hermes-agent/venv/bin/pip install yfinance` if not present.
2. Phase 2 — portfolio & risk engines.
3. … through Phase 6 — independence (own runtime/tool registry/substrate).

## Resume commands

```bash
hermes -p f1nance                        # interactive
hermes -p f1nance chat -q "value NVDA"   # one-shot

# rebase upstream (keep the hardfork current)
cd "/home/mustbearn/Projects/AI Agents/F1NANCE Agent" && git fetch origin && git rebase origin/main

# re-project repo → profile after editing f1nance/
cp f1nance/SOUL.md ~/.hermes/profiles/f1nance/SOUL.md
cp -r f1nance/skills/* ~/.hermes/profiles/f1nance/skills/finance/
```
