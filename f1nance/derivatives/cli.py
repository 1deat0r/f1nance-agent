"""Command-line entry point for the F1NANCE derivatives engine.

Run with::

    f1nance/.venv/bin/python -m f1nance.derivatives price spec.json
    f1nance/.venv/bin/python -m f1nance.derivatives greeks spec.json
    f1nance/.venv/bin/python -m f1nance.derivatives implied_vol spec.json
    f1nance/.venv/bin/python -m f1nance.derivatives binomial spec.json

Emits JSON to stdout. Every command reads a JSON spec file (``-`` for stdin).

Spec shapes (``r``, ``sigma``, ``q`` are annualized decimal; ``T`` in years)::

    # price — Black-Scholes European value
    {"call_put": "call", "S": 100, "K": 100, "T": 1, "r": 0.05,
     "sigma": 0.20, "q": 0}

    # greeks — closed-form delta/gamma/vega/theta/rho
    {"call_put": "put", "S": 100, "K": 100, "T": 1, "r": 0.05,
     "sigma": 0.20, "q": 0}

    # implied_vol — solve volatility from a market price
    {"price": 10.45, "call_put": "call", "S": 100, "K": 100, "T": 1,
     "r": 0.05, "q": 0}

    # binomial — CRR lattice (European unless american=true)
    {"call_put": "put", "S": 42, "K": 40, "T": 0.5, "r": 0.10,
     "sigma": 0.20, "steps": 500, "american": true}
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, Optional

from .binomial import binomial_price
from .black_scholes import black_scholes, greeks, implied_volatility


def _load(path: str) -> Any:
    raw = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(raw)


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _num(spec: dict, key: str, default: float) -> float:
    return float(spec.get(key, default))


def cmd_price(spec: dict) -> None:
    cp = str(spec["call_put"])
    result = black_scholes(
        cp,
        float(spec["S"]),
        float(spec["K"]),
        float(spec["T"]),
        _num(spec, "r", 0.0),
        float(spec["sigma"]),
        q=_num(spec, "q", 0.0),
    )
    _emit({"call_put": cp.lower(), **asdict(result)})


def cmd_greeks(spec: dict) -> None:
    cp = str(spec["call_put"])
    result = greeks(
        cp,
        float(spec["S"]),
        float(spec["K"]),
        float(spec["T"]),
        _num(spec, "r", 0.0),
        float(spec["sigma"]),
        q=_num(spec, "q", 0.0),
    )
    _emit({"call_put": cp.lower(), **asdict(result)})


def cmd_implied_vol(spec: dict) -> None:
    _emit(
        {
            "implied_volatility": implied_volatility(
                float(spec["price"]),
                str(spec["call_put"]),
                float(spec["S"]),
                float(spec["K"]),
                float(spec["T"]),
                _num(spec, "r", 0.0),
                q=_num(spec, "q", 0.0),
            )
        }
    )


def cmd_binomial(spec: dict) -> None:
    cp = str(spec["call_put"])
    _emit(
        {
            "call_put": cp.lower(),
            "price": binomial_price(
                cp,
                float(spec["S"]),
                float(spec["K"]),
                float(spec["T"]),
                _num(spec, "r", 0.0),
                float(spec["sigma"]),
                q=_num(spec, "q", 0.0),
                steps=int(spec.get("steps", 200)),
                american=bool(spec.get("american", False)),
            ),
            "steps": int(spec.get("steps", 200)),
            "american": bool(spec.get("american", False)),
        }
    )


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1nance.derivatives",
        description="F1NANCE derivatives engine (stdlib-only).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name, help_ in (
        ("price", "Black-Scholes European option value"),
        ("greeks", "closed-form delta/gamma/vega/theta/rho"),
        ("implied_vol", "solve volatility implied by a market price"),
        ("binomial", "CRR binomial tree (European or American)"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    args = parser.parse_args(argv)
    try:
        spec = _load(args.spec)
        handlers = {
            "price": cmd_price,
            "greeks": cmd_greeks,
            "implied_vol": cmd_implied_vol,
            "binomial": cmd_binomial,
        }
        handlers[args.cmd](spec)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
