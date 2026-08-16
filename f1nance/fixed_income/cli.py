"""Command-line entry point for the F1NANCE fixed-income engine.

Run with::

    f1nance/.venv/bin/python -m f1nance.fixed_income price spec.json
    f1nance/.venv/bin/python -m f1nance.fixed_income ytm spec.json
    f1nance/.venv/bin/python -m f1nance.fixed_income duration spec.json
    f1nance/.venv/bin/python -m f1nance.fixed_income pv spec.json
    f1nance/.venv/bin/python -m f1nance.fixed_income pv_curve spec.json
    f1nance/.venv/bin/python -m f1nance.fixed_income forward spec.json
    f1nance/.venv/bin/python -m f1nance.fixed_income bootstrap spec.json

Emits JSON to stdout. Every command reads a JSON spec file (``-`` for stdin).

Spec shapes::

    # price — clean price of a bond
    {"coupon_rate": 0.05, "maturity_years": 10, "ytm": 0.04,
     "face": 100, "payments_per_year": 2}

    # ytm — solve yield-to-maturity from a clean price
    {"price": 108.17, "coupon_rate": 0.05, "maturity_years": 10,
     "face": 100, "payments_per_year": 2}

    # duration — Macaulay/modified duration, convexity, DV01
    {"coupon_rate": 0.05, "maturity_years": 10, "ytm": 0.04,
     "face": 100, "payments_per_year": 2}

    # pv — present value at a flat rate
    {"cashflows": [5, 5, 105], "times": [1, 2, 3], "rate": 0.04,
     "compounding": 2}

    # pv_curve — present value along an interpolated spot curve
    {"cashflows": [5, 5, 105], "times": [1, 2, 3],
     "tenors": [1, 2, 3, 5, 10], "spots": [0.02, 0.025, 0.03, 0.035, 0.04],
     "compounding": 2}

    # forward — implied forward rate between two tenors
    {"rate_t1": 0.02, "rate_t2": 0.03, "t1": 1, "t2": 2, "compounding": 2}

    # bootstrap — par → spot curve (annual-coupon par bonds, tenors 1..N)
    {"par_tenors": [1, 2, 3], "par_yields": [0.02, 0.025, 0.03]}
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, Optional

from .bonds import bond_price, duration_and_convexity, ytm
from .curves import bootstrap_spot_curve, forward_rate, pv, pv_curve


def _load(path: str) -> Any:
    raw = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(raw)


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _num(spec: dict, key: str, default: float) -> float:
    return float(spec.get(key, default))


def cmd_price(spec: dict) -> None:
    _emit(
        {
            "price": bond_price(
                _num(spec, "coupon_rate", 0.0),
                _num(spec, "maturity_years", 0.0),
                _num(spec, "ytm", 0.0),
                face=_num(spec, "face", 100.0),
                payments_per_year=int(spec.get("payments_per_year", 2)),
            )
        }
    )


def cmd_ytm(spec: dict) -> None:
    _emit(
        {
            "ytm": ytm(
                float(spec["price"]),
                _num(spec, "coupon_rate", 0.0),
                _num(spec, "maturity_years", 0.0),
                face=_num(spec, "face", 100.0),
                payments_per_year=int(spec.get("payments_per_year", 2)),
            )
        }
    )


def cmd_duration(spec: dict) -> None:
    result = duration_and_convexity(
        _num(spec, "coupon_rate", 0.0),
        _num(spec, "maturity_years", 0.0),
        _num(spec, "ytm", 0.0),
        face=_num(spec, "face", 100.0),
        payments_per_year=int(spec.get("payments_per_year", 2)),
    )
    _emit(asdict(result))


def cmd_pv(spec: dict) -> None:
    _emit(
        {
            "pv": pv(
                [float(c) for c in spec["cashflows"]],
                [float(t) for t in spec["times"]],
                float(spec["rate"]),
                compounding=spec.get("compounding", 2),
            )
        }
    )


def cmd_pv_curve(spec: dict) -> None:
    _emit(
        {
            "pv": pv_curve(
                [float(c) for c in spec["cashflows"]],
                [float(t) for t in spec["times"]],
                [float(t) for t in spec["tenors"]],
                [float(s) for s in spec["spots"]],
                compounding=spec.get("compounding", 2),
            )
        }
    )


def cmd_forward(spec: dict) -> None:
    _emit(
        {
            "forward_rate": forward_rate(
                float(spec["rate_t1"]),
                float(spec["rate_t2"]),
                float(spec["t1"]),
                float(spec["t2"]),
                compounding=spec.get("compounding", 2),
            )
        }
    )


def cmd_bootstrap(spec: dict) -> None:
    tenors, spots = bootstrap_spot_curve(
        [float(t) for t in spec["par_tenors"]],
        [float(y) for y in spec["par_yields"]],
    )
    _emit({"tenors": tenors, "spots": spots})


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1nance.fixed_income",
        description="F1NANCE fixed-income engine (stdlib-only).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name, help_ in (
        ("price", "clean price of a bond at a given yield"),
        ("ytm", "yield-to-maturity from a clean price"),
        ("duration", "Macaulay/modified duration, convexity, DV01"),
        ("pv", "present value at a flat rate"),
        ("pv_curve", "present value along an interpolated spot curve"),
        ("forward", "implied forward rate between two tenors"),
        ("bootstrap", "bootstrap a spot curve from par yields"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    args = parser.parse_args(argv)
    try:
        spec = _load(args.spec)
        handlers = {
            "price": cmd_price,
            "ytm": cmd_ytm,
            "duration": cmd_duration,
            "pv": cmd_pv,
            "pv_curve": cmd_pv_curve,
            "forward": cmd_forward,
            "bootstrap": cmd_bootstrap,
        }
        handlers[args.cmd](spec)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
