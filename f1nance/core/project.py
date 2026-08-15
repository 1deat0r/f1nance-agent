"""Projector — render the store into derived views.

The store is canonical; the working files are derived. ``render_markdown``
folds active facts into a single STATE document with one section per kind,
and ``write_view`` persists it. In the Hermes bootstrap the profile's
MEMORY.md / USER.md are exactly this projection; on the way out (Phase 6)
the standalone agent's own working files take their place. Either way, the
rule is the same: generate from the store, never hand-edit the derived file.
"""

from __future__ import annotations

from pathlib import Path

from .memory import KINDS, MemoryStore

KIND_TITLES = {
    "identity": "Identity",
    "directive": "Directives",
    "user": "Operator (1deat0r)",
    "memory": "Memory",
    "decision": "Decisions",
}


def render_markdown(store: MemoryStore, title: str = "# F1NANCE STATE") -> str:
    """Render the active facts as a markdown STATE document.

    One section per non-empty kind, in canonical order. Retracted and
    superseded facts are excluded — the derived view shows only what is
    currently true, while the store retains the full trail.
    """
    lines = [
        title,
        "",
        "_Derived view — generated from the provenance store. The store is "
        "canonical; edit it, never this file._",
        "",
    ]
    for kind in KINDS:
        facts = store.active(kind=kind)
        if not facts:
            continue
        lines.append(f"## {KIND_TITLES.get(kind, kind.title())}")
        lines.append("")
        for f in facts:
            src = f" _[{f.source}]_" if f.source else ""
            lines.append(f"- {f.content}{src}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_json(store: MemoryStore) -> dict:
    """Active facts grouped by kind, as a plain dict of content lines."""
    return store.export()


def write_view(store: MemoryStore, path: str | Path) -> Path:
    """Persist the markdown derived view to ``path`` and return it."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(store), encoding="utf-8")
    return out
