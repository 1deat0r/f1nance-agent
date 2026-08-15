"""Command-line entry point for the F1NANCE store-first core.

Run with::

    f1nance/.venv/bin/python -m f1nance.core record spec.json
    f1nance/.venv/bin/python -m f1nance.core retract <id>
    f1nance/.venv/bin/python -m f1nance.core export
    f1nance/.venv/bin/python -m f1nance.core history <id>
    f1nance/.venv/bin/python -m f1nance.core render --out STATE.md

Every command accepts ``--store`` (default ``f1nance/core/store.json``,
relative to the repo root). Commands emit JSON to stdout; ``render`` also
writes a markdown derived view to ``--out``.

Spec shape for ``record``::

    {
      "content": "...", "kind": "memory", "source": "foreground",
      "supersedes": ["abc123"], "note": "..."
    }

``kind`` is one of ``identity``, ``directive``, ``user``, ``memory``,
``decision``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, Optional

from .memory import MemoryStore
from .project import write_view

DEFAULT_STORE = "f1nance/core/store.json"


def _load(path: str) -> Any:
    raw = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(raw)


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_record(spec: dict, store_path: str) -> None:
    store = MemoryStore(store_path)
    with store.mutate():
        fact = store.add(
            content=str(spec.get("content", "")),
            kind=str(spec.get("kind", "memory")),
            source=str(spec.get("source", "")),
            supersedes=list(spec.get("supersedes", [])),
            note=str(spec.get("note", "")),
        )
    _emit(asdict(fact))


def cmd_retract(fact_id: str, store_path: str) -> None:
    store = MemoryStore(store_path)
    with store.mutate():
        fact = store.retract(fact_id, source="cli")
    _emit(asdict(fact) if fact is not None else None)


def cmd_export(store_path: str) -> None:
    _emit(MemoryStore(store_path).export())


def cmd_history(fact_id: str, store_path: str) -> None:
    store = MemoryStore(store_path)
    _emit([asdict(f) for f in store.history(fact_id)])


def cmd_render(store_path: str, out_path: str) -> None:
    store = MemoryStore(store_path)
    path = write_view(store, out_path)
    _emit({"path": str(path), "active_facts": sum(len(v) for v in store.export().values())})


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1nance.core",
        description="F1NANCE store-first core (provenance-aware memory).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    record_p = sub.add_parser("record", help="append a fact to the store")
    record_p.add_argument("spec", help="path to JSON spec, or '-' for stdin")
    record_p.add_argument("--store", default=DEFAULT_STORE)

    retract_p = sub.add_parser("retract", help="retract an active fact")
    retract_p.add_argument("fact_id", help="the fact id to retract")
    retract_p.add_argument("--store", default=DEFAULT_STORE)

    export_p = sub.add_parser("export", help="active facts grouped by kind")
    export_p.add_argument("--store", default=DEFAULT_STORE)

    history_p = sub.add_parser("history", help="a fact's full supersede/retract chain")
    history_p.add_argument("fact_id", help="the fact id to trace")
    history_p.add_argument("--store", default=DEFAULT_STORE)

    render_p = sub.add_parser("render", help="render the markdown derived view")
    render_p.add_argument("--store", default=DEFAULT_STORE)
    render_p.add_argument("--out", default="f1nance/core/STATE.md")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "record":
            cmd_record(_load(args.spec), args.store)
        elif args.cmd == "retract":
            cmd_retract(args.fact_id, args.store)
        elif args.cmd == "export":
            cmd_export(args.store)
        elif args.cmd == "history":
            cmd_history(args.fact_id, args.store)
        elif args.cmd == "render":
            cmd_render(args.store, args.out)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
