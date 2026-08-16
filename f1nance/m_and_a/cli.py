"""Command-line entry point for the F1NANCE M&A engine.

Run with::

    f1nance/.venv/bin/python -m f1nance.m_and_a accretion spec.json
    f1nance/.venv/bin/python -m f1nance.m_and_a synergies spec.json
    f1nance/.venv/bin/python -m f1nance.m_and_a breakeven spec.json
    f1nance/.venv/bin/python -m f1nance.m_and_a lbo spec.json

Emits JSON to stdout. Every command reads a JSON spec file (``-`` for stdin).

Spec shapes (money in one currency; rates/tax/margins are decimals):::

    # accretion — pro-forma EPS and accretion/dilution of a cash/stock merger
    {"acquirer_ni": 500, "acquirer_shares": 100, "target_ni": 120,
     "purchase_price": 2000, "cash_portion": 1000, "stock_portion": 1000,
     "acquirer_share_price": 50, "tax_rate": 0.25,
     "cost_synergies": 80, "new_debt_rate": 0.05, "cash_used": 0, "cash_yield": 0}

    # synergies — PV the run-rate synergies, net of integration costs + premium
    {"cost_synergies": 100, "revenue_synergies": 0, "revenue_margin": 0,
     "tax_rate": 0.25, "discount_rate": 0.10, "ramp_years": 2,
     "integration_costs": 50, "premium_paid": 400, "growth": 0}

    # breakeven — run-rate cost synergies required to justify the premium
    {"premium_paid": 400, "integration_costs": 50, "tax_rate": 0.25,
     "discount_rate": 0.10, "ramp_years": 2, "growth": 0}

    # lbo — leveraged buyout: sources & uses, debt schedule, MOIC/IRR
    {"enterprise_value": 1000, "existing_net_debt": 200, "fees": 30,
     "entry_debt": 700, "ebitda_0": 100, "ebitda_growth": 0.05, "years": 5,
     "fcf_margin": 0.60, "exit_multiple": 8.0, "interest_rate": 0.06,
     "tax_rate": 0.25}
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, Optional

from .accretion_dilution import accretion_dilution
from .lbo import lbo
from .synergies import synergy_breakeven, synergy_value


def _load(path: str) -> Any:
    raw = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(raw)


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _num(spec: dict, key: str, default: float) -> float:
    return float(spec.get(key, default))


def cmd_accretion(spec: dict) -> None:
    result = accretion_dilution(
        _num(spec, "acquirer_ni", 0.0),
        float(spec["acquirer_shares"]),
        _num(spec, "target_ni", 0.0),
        float(spec["purchase_price"]),
        float(spec["cash_portion"]),
        float(spec["stock_portion"]),
        _num(spec, "acquirer_share_price", 0.0),
        float(spec["tax_rate"]),
        cost_synergies=_num(spec, "cost_synergies", 0.0),
        revenue_synergies=_num(spec, "revenue_synergies", 0.0),
        new_debt_rate=_num(spec, "new_debt_rate", 0.0),
        cash_used=_num(spec, "cash_used", 0.0),
        cash_yield=_num(spec, "cash_yield", 0.0),
    )
    _emit(asdict(result))


def cmd_synergies(spec: dict) -> None:
    result = synergy_value(
        _num(spec, "cost_synergies", 0.0),
        _num(spec, "revenue_synergies", 0.0),
        _num(spec, "revenue_margin", 0.0),
        float(spec["tax_rate"]),
        float(spec["discount_rate"]),
        int(spec["ramp_years"]),
        _num(spec, "integration_costs", 0.0),
        float(spec["premium_paid"]),
        growth=_num(spec, "growth", 0.0),
    )
    _emit(asdict(result))


def cmd_breakeven(spec: dict) -> None:
    result = synergy_breakeven(
        float(spec["premium_paid"]),
        _num(spec, "integration_costs", 0.0),
        float(spec["tax_rate"]),
        float(spec["discount_rate"]),
        int(spec["ramp_years"]),
        growth=_num(spec, "growth", 0.0),
    )
    _emit(asdict(result))


def cmd_lbo(spec: dict) -> None:
    result = lbo(
        float(spec["enterprise_value"]),
        _num(spec, "existing_net_debt", 0.0),
        _num(spec, "fees", 0.0),
        float(spec["entry_debt"]),
        float(spec["ebitda_0"]),
        float(spec["ebitda_growth"]),
        int(spec["years"]),
        float(spec["fcf_margin"]),
        float(spec["exit_multiple"]),
        float(spec["interest_rate"]),
        tax_rate=_num(spec, "tax_rate", 0.0),
    )
    _emit(asdict(result))


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1nance.m_and_a",
        description="F1NANCE M&A engine (stdlib-only).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name, help_ in (
        ("accretion", "pro-forma EPS and accretion/dilution of a merger"),
        ("synergies", "present-value the synergies, net of costs and premium"),
        ("breakeven", "run-rate synergies required to justify the premium"),
        ("lbo", "leveraged buyout: sources & uses, debt schedule, MOIC/IRR"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    args = parser.parse_args(argv)
    try:
        spec = _load(args.spec)
        handlers = {
            "accretion": cmd_accretion,
            "synergies": cmd_synergies,
            "breakeven": cmd_breakeven,
            "lbo": cmd_lbo,
        }
        handlers[args.cmd](spec)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
