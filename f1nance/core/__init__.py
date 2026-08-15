"""F1NANCE core — the Phase-5 store-first evolution loop.

Hermes-independent, stdlib-only. This is the substrate that will host
F1NANCE's durable identity, memory, and decisions once it leaves the Hermes
chassis: an append-only, provenance-aware store where facts carry a source
and conflicts are flagged and linked (supersede/retract), never silently
overwritten. The Hermes profile (and later the standalone agent's working
files) are a *derived view* of this store — the repo is the body.

Two modules:

- ``memory`` — the ``MemoryStore`` (``Fact`` with supersede/retract chains,
  ``history()`` audit, cross-process advisory lock).
- ``project`` — the projector that renders the active facts into a markdown
  STATE document (the derived view) and a JSON export.
"""

from .memory import KINDS, RETRACTED, Fact, MemoryStore, locked
from .project import render_json, render_markdown, write_view

__version__ = "0.1.0"

__all__ = [
    "Fact",
    "MemoryStore",
    "KINDS",
    "RETRACTED",
    "locked",
    "render_json",
    "render_markdown",
    "write_view",
    "__version__",
]
