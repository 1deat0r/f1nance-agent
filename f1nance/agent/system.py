"""The agent's system prompt — SOUL + durable state + the working contract.

The system prompt is the standalone agent's identity-in-context. It is built
from three parts, all deterministic:

1. ``SOUL.md`` (the immutable identity, beliefs, and Prime Directive);
2. the active facts from the provenance store (identity/directive/user/memory/
   decision), rendered as a "Memory" section so the agent wakes with its
   durable state rather than a blank recollection;
3. a short working contract that tells the agent it has tools, which tools,
   and the guardrails that govern how it uses them.

``build_system_prompt`` is pure (soul text + facts → string) so it is fully
offline-testable; ``load_system_prompt`` wires it to the canonical files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..core.memory import MemoryStore
from ..core.project import KIND_TITLES
from .paths import default_soul_path, default_store_path

# The working contract is stable prose appended after SOUL + memory. It is the
# one place the runtime *instructs* the model about its tools and guardrails;
# everything else is the SOUL's own voice.
WORKING_CONTRACT = """\
## How you work

You are running on your own standalone runtime (`f1nance/agent`) — not inside
Hermes. You have tools for real market data, the portfolio/risk engine, the
quant & backtesting engine, the fixed-income engine (bonds, yield curves,
duration), the derivatives engine (options, Greeks, implied vol), the
risk-management engine (limits, stress tests, VaR backtesting), the M&A
engine (accretion/dilution, synergies, LBO), the deal-memo pipeline (one
scored verdict over a whole deal: valuation → M&A → risk), the execution &
compliance layer, the multi-seat desk, and your provenance store. Use them to
gather real data and compute real numbers before you answer.

Guardrails, always on:

- No fabrication. Never invent a price, a quote, a return, a filing, or a data
  point. If a source is unavailable, say the data is unavailable — do not
  simulate it and pass it off as real.
- Risk before return. Every investment view names the loss case and its
  approximate size before the upside.
- Confidence calibration. Confidence reflects evidence, not bravado; a view
  without a falsification condition is not a view.
- Suitability. Size recommendations to 1deat0r's objectives, horizon, and risk
  capacity — never activity for its own sake.
- Not-a-license. You are analysis, not authorization. You never present output
  as binding advice that replaces a licensed professional where the law
  requires one.

Your durable facts live in the provenance store. When a fact about yourself,
about 1deat0r, or about your environment changes, record it with
`memory_record` (superseding the old fact) so the change survives this
session. Decisions worth keeping — what you chose and why — belong in the
store as `decision` facts."""


def build_system_prompt(soul_text: str, facts: Optional[dict] = None) -> str:
    """Build the system prompt from SOUL text and the active store facts.

    ``facts`` is the store's ``export()`` shape: a dict of kind → list of
    content strings. Kinds with no active facts are omitted; when the store is
    entirely empty, a single placeholder line says so.
    """
    sections: list = [soul_text.strip(), "", "## Memory (durable state)", ""]
    facts = facts or {}
    if not any(facts.values()):
        sections.append("_No durable facts recorded yet._")
        sections.append("")
    for kind, title in KIND_TITLES.items():
        lines = facts.get(kind)
        if not lines:
            continue
        sections.append(f"### {title}")
        sections.append("")
        for line in lines:
            sections.append(f"- {line}")
        sections.append("")
    sections.append(WORKING_CONTRACT)
    return "\n".join(sections).strip() + "\n"


def load_system_prompt(
    soul_path: Optional[str] = None, store: Optional[MemoryStore] = None
) -> str:
    """Load SOUL.md and the store, and build the system prompt.

    Defaults resolve to the canonical body files (``f1nance/SOUL.md`` and
    ``f1nance/core/store.json``) regardless of the process CWD.
    """
    path = Path(soul_path) if soul_path else default_soul_path()
    soul = path.read_text(encoding="utf-8")
    if store is None:
        store = MemoryStore(default_store_path())
    return build_system_prompt(soul, store.export())


__all__ = [
    "KIND_TITLES",
    "WORKING_CONTRACT",
    "build_system_prompt",
    "load_system_prompt",
]
