"""Command-line entry point for the F1NANCE desk.

Run with::

    f1nance/.venv/bin/python -m f1nance.desk seats
    f1nance/.venv/bin/python -m f1nance.desk route spec.json
    f1nance/.venv/bin/python -m f1nance.desk run spec.json

Emits JSON to stdout.

Spec shapes::

    # route / run — a brief
    {
      "objective": "Should we trim the concentrated AAPL position?",
      "context": "...", "horizon": "12m", "risk_capacity": "moderate",
      "constraints": ["no new single name > 20%"], "seats": ["pm", "trader"],

      # run additionally requires pre-authored findings, keyed by seat:
      "findings": {
        "pm": {"thesis": "...", "stance": "bearish", "confidence": 0.7,
               "loss_case": "...", "falsify": "...", "actions": ["trim to 15%"]},
        "trader": {"thesis": "...", "stance": "neutral", "confidence": 0.5,
                   "loss_case": "...", "falsify": "..."}
      }
    }

``run`` does not call a model: the offline CLI's executor is scripted from
the ``findings`` map, so it exercises the real route → dispatch → validate →
aggregate path deterministically. A live runtime supplies a real executor
instead (see ``desk.py``); the coordination logic is identical.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional

from .brief import Brief, Verdict
from .desk import Desk, scripted_executor
from .seats import DESK_SEATS, Seat, route

_CONFIDENCE_LABELS = {"high": 0.8, "medium": 0.5, "low": 0.2}


def _load(path: str) -> Any:
    raw = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(raw)


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _confidence(value) -> float:
    if isinstance(value, str):
        v = value.strip().lower()
        if v in _CONFIDENCE_LABELS:
            return _CONFIDENCE_LABELS[v]
        try:
            return float(v)
        except ValueError:
            raise ValueError(
                f"confidence {value!r} is not a number or high/medium/low"
            ) from None
    return float(value)


def _seat_dict(seat: Seat) -> dict:
    return {
        "name": seat.name,
        "label": seat.label,
        "domain": seat.domain,
        "roles": list(seat.roles),
        "engines": list(seat.engines),
        "keywords": list(seat.keywords),
        "mandate": seat.mandate,
    }


def _brief_from_spec(spec: dict) -> Brief:
    return Brief(
        objective=str(spec.get("objective", "")),
        context=str(spec.get("context", "")),
        horizon=str(spec.get("horizon", "")),
        risk_capacity=str(spec.get("risk_capacity", "")),
        constraints=tuple(spec.get("constraints", ())),
        seats=tuple(spec.get("seats", ())),
    )


def _verdict_dict(v: Verdict) -> dict:
    return {
        "objective": v.brief.objective,
        "stance": v.stance,
        "agreement": v.agreement,
        "dissent": list(v.dissent),
        "confidence": v.confidence,
        "findings": [
            {
                "seat": f.seat,
                "stance": f.stance,
                "confidence": f.confidence,
                "thesis": f.thesis,
                "loss_case": f.loss_case,
                "falsify": f.falsify,
                "actions": list(f.actions),
            }
            for f in v.findings
        ],
    }


def cmd_seats() -> None:
    _emit({"seats": [_seat_dict(s) for s in DESK_SEATS.values()]})


def cmd_route(spec: dict) -> None:
    brief = _brief_from_spec(spec)
    seated = route(brief.objective, brief.seats)
    _emit({
        "objective": brief.objective,
        "seats": [s.name for s in seated],
        "domains": [s.domain for s in seated],
    })


def cmd_run(spec: dict) -> None:
    brief = _brief_from_spec(spec)
    findings_spec = spec.get("findings")
    if not isinstance(findings_spec, dict) or not findings_spec:
        raise ValueError(
            "run requires a 'findings' map keyed by seat "
            "(the offline executor is scripted)"
        )
    for key, fspec in findings_spec.items():
        fspec = dict(fspec)
        fspec["seat"] = key
        if "confidence" in fspec:
            fspec["confidence"] = _confidence(fspec["confidence"])
        findings_spec[key] = fspec
    verdict = Desk().run(brief, scripted_executor(findings_spec))
    _emit(_verdict_dict(verdict))


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1nance.desk",
        description="F1NANCE desk — multi-agent coordination (stdlib-only).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seats", help="dump the five-seat roster")

    route_p = sub.add_parser("route", help="route a brief to seats")
    route_p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    run_p = sub.add_parser("run", help="run a brief with scripted findings")
    run_p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "seats":
            cmd_seats()
        elif args.cmd == "route":
            cmd_route(_load(args.spec))
        elif args.cmd == "run":
            cmd_run(_load(args.spec))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
