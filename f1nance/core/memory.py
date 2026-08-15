"""F1NANCE core memory — a provenance-aware, versioned memory/decision store.

This is the Phase-5 store-first evolution loop: the substrate that will host
F1NANCE's durable identity, memory, and decisions once it leaves the Hermes
chassis (see ROADMAP.md → Phase 6). It applies one lesson from the 3V0
Agent's native core: facts carry provenance, and conflicts are FLAGGED and
linked, never silently overwritten.

Design:

- Every fact has an id, kind, source, and creation timestamp.
- A new fact that contradicts an old one SUPERSEDES it: the old fact is marked
  inactive (still queryable via ``history()``) and linked to its successor.
  Nothing is destroyed — the audit trail is the point.
- ``decision`` is a distinct kind from the execution ledger's trade log: the
  ledger mirrors *trading* decisions (what to buy/sell); this store mirrors
  *agent* decisions (what F1NANCE chose to do and why) plus the durable
  facts, beliefs, and directives that shape those choices.
- Plain JSON on disk (stdlib only) so the source of truth is auditable in the
  body repo — the repo is the body, the Hermes profile is a derived view.
"""

from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path

# fcntl is Unix-only; on Windows there is no equivalent advisory lock exposed
# by the stdlib, so locking degrades to a no-op there (the store is
# single-host by design).
try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

# Canonical display order for rendering; validation uses the set.
KINDS = ("identity", "directive", "user", "memory", "decision")
_VALID_KINDS = set(KINDS)

# ``superseded_by`` sentinel for a fact that was REMOVED (no successor
# exists). Distinct from a real fact id, so ``history()`` terminates the
# chain at the retracted fact and ``active()``/``export()`` exclude it.
RETRACTED = "retracted"


@contextmanager
def locked(path: str | Path):
    """Serialize cross-process read-modify-write on the store at ``path``.

    An advisory ``flock`` on a ``<store>.lock`` sidecar so concurrent writers
    (a foreground recorder and a background evolution loop) cannot interleave
    load→mutate→save on the same JSON file. Degrades to a no-op where
    ``fcntl`` is unavailable.
    """
    lock_path = Path(path).with_suffix(Path(path).suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if fcntl is None:
        yield
        return
    fd = open(lock_path, "a+", encoding="utf-8")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        fd.close()


@dataclass
class Fact:
    id: str
    content: str
    kind: str                  # identity | directive | user | memory | decision
    source: str                # e.g. "foreground", "background", "1deat0r"
    created_at: str
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str = ""    # non-empty => inactive
    note: str = ""

    @property
    def active(self) -> bool:
        return not self.superseded_by


class MemoryStore:
    """Append-only memory with supersession (no silent overwrite)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.facts: list[Fact] = []
        if self.path.exists():
            self._load()

    # -- persistence -------------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            self.facts = []
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.facts = [Fact(**f) for f in raw.get("facts", [])]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "facts": [asdict(f) for f in self.facts]}
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # -- mutations ---------------------------------------------------------

    def add(
        self,
        content: str,
        kind: str,
        source: str,
        supersedes: list[str] | None = None,
        note: str = "",
        persist: bool = True,
    ) -> Fact:
        if kind not in _VALID_KINDS:
            raise ValueError(f"kind must be one of {sorted(_VALID_KINDS)}, got {kind!r}")
        if not (content or "").strip():
            raise ValueError("a fact needs content")
        fact = Fact(
            id=uuid.uuid4().hex[:12],
            content=content.strip(),
            kind=kind,
            source=source,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            supersedes=list(supersedes or []),
            note=note,
        )
        self.facts.append(fact)
        # Link superseded facts to their successor (conflict flagged, not erased).
        for target_id in fact.supersedes:
            for old in self.facts:
                if old.id == target_id and old.active:
                    old.superseded_by = fact.id
        if persist:
            self._save()
        return fact

    def retract(self, fact_id: str, source: str = "", persist: bool = True) -> Fact | None:
        """Mark an active fact as removed (no successor exists).

        A removal has no successor, so ``superseded_by`` is set to the
        ``RETRACTED`` sentinel, which excludes the fact from
        ``active()``/``export()`` and makes ``history()`` stop at it as a
        terminal. Nothing is destroyed — the retracted fact remains in the
        store and is recoverable by id/history.
        """
        f = self.get(fact_id)
        if f is None or not f.active:
            return None
        f.superseded_by = RETRACTED
        if source:
            tag = f"retracted by {source}"
            f.note = f"{f.note} {tag}".strip() if f.note else tag
        if persist:
            self._save()
        return f

    def reload(self) -> None:
        """Re-read the store from disk, replacing in-memory facts.

        Used inside ``mutate()`` so a writer operating under the
        cross-process lock always applies its mutation to the latest facts.
        """
        self._load()

    @contextmanager
    def mutate(self):
        """Acquire the cross-process lock, reload latest facts, then yield.

        The canonical pattern for a store writer::

            store = MemoryStore(path)
            with store.mutate():
                ...  # add/retract — each mutation persists
        """
        with locked(self.path):
            self.reload()
            yield self

    # -- queries -----------------------------------------------------------

    def active(self, kind: str | None = None) -> list[Fact]:
        out = [f for f in self.facts if f.active]
        if kind is not None:
            out = [f for f in out if f.kind == kind]
        return out

    def get(self, fact_id: str) -> Fact | None:
        for f in self.facts:
            if f.id == fact_id:
                return f
        return None

    def history(self, fact_id: str) -> list[Fact]:
        """Reconstruct a fact's full chain, oldest -> newest.

        Walks ``superseded_by`` forward to the newest link, then
        ``supersedes`` backward to the oldest, so an audit of any fact
        recovers the whole thread of what it replaced and what replaced it.
        """
        by_id = {f.id: f for f in self.facts}
        cur = by_id.get(fact_id)
        if cur is None:
            return []
        while cur.superseded_by and cur.superseded_by in by_id:
            cur = by_id[cur.superseded_by]
        chain: list[Fact] = []
        seen: set[str] = set()
        while cur is not None and cur.id not in seen:
            chain.append(cur)
            seen.add(cur.id)
            prev = None
            for fid in cur.supersedes:
                if fid in by_id:
                    prev = by_id[fid]
                    break
            cur = prev
        chain.reverse()
        return chain

    # -- export ------------------------------------------------------------

    def export(self) -> dict[str, list[str]]:
        """Active facts grouped by kind, as plain text lines (derived view)."""
        out: dict[str, list[str]] = {}
        for kind in KINDS:
            lines = [f.content for f in self.active(kind=kind)]
            if lines:
                out[kind] = lines
        return out
