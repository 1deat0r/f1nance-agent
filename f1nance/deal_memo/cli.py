"""Command-line entry point for the F1NANCE deal-memo engine.

Run with::

    f1nance/.venv/bin/python -m f1nance.deal_memo memo spec.json

Emits the memo as JSON to stdout. The spec is one JSON object (``-`` for
stdin) with three optional blocks — ``merger``, ``lbo``, and ``risk`` — plus
optional ``deal_id`` / ``names`` / ``loss_cases`` / ``falsify``. See
``f1nance.deal_memo.build_deal_memo`` for the full field contract.

Spec shape (money in one currency; rates/tax/margins/shocks are decimals)::

    {
      "deal_id": "acme-buys-beta",
      "names": {"acquirer": "Acme", "target": "Beta"},

      "merger": {
        "acquirer_ni": 500, "acquirer_shares": 100, "target_ni": 120,
        "purchase_price": 2000, "cash_portion": 1000, "stock_portion": 1000,
        "acquirer_share_price": 50, "tax_rate": 0.25,
        "cost_synergies": 100, "new_debt_rate": 0.05,
        "discount_rate": 0.10, "ramp_years": 2,
        "premium_paid": 400, "integration_costs": 50
      },

      "lbo": {
        "enterprise_value": 1000, "existing_net_debt": 200, "fees": 30,
        "entry_debt": 700, "ebitda_0": 100, "ebitda_growth": 0.05,
        "years": 5, "fcf_margin": 0.60, "exit_multiple": 8.0,
        "interest_rate": 0.06, "tax_rate": 0.25, "hurdle_irr": 0.15
      },

      "risk": {
        "nav": 30520,
        "metrics": {"gross_exposure": 1.20},
        "limits": [{"name": "gross exposure", "metric": "gross_exposure",
                    "threshold": 1.50, "direction": "max"}],
        "exposures": {"equity": 20000.0, "rates": -5000.0},
        "scenarios": [{"name": "equity -30%", "shocks": {"equity": -0.30}}],
        "loss_budget": 5000
      }
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, Optional

from .memo import build_deal_memo


def _load(path: str) -> Any:
    raw = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(raw)


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_memo(spec: dict) -> None:
    _emit(asdict(build_deal_memo(spec)))


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1nance.deal_memo",
        description="F1NANCE deal-memo engine (stdlib-only).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser(
        "memo", help="score a whole deal: accretion, synergies, LBO, risk, one verdict"
    )
    p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    args = parser.parse_args(argv)
    try:
        spec = _load(args.spec)
        handlers = {"memo": cmd_memo}
        handlers[args.cmd](spec)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
