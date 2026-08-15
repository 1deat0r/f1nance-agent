"""Command-line entry point for the F1NANCE execution & compliance layer.

Run with::

    f1nance/.venv/bin/python -m f1nance.execution order spec.json
    f1nance/.venv/bin/python -m f1nance.execution impact spec.json
    f1nance/.venv/bin/python -m f1nance.execution ledger spec.json [--out ledger.jsonl]
    f1nance/.venv/bin/python -m f1nance.execution export ledger.jsonl

Emits JSON to stdout. Each command reads a JSON spec file (``-`` for stdin)
except ``export``, which reads a persisted ledger file.

Spec shapes::

    # order — validate + assess + (optionally) cost an order
    {
      "instrument": "AAPL", "side": "buy", "quantity": 100,
      "order_type": "limit", "limit_price": 190.0,
      "market_price": 192.0,          # optional: marketable / stop-side checks
      "adv": 50000000.0,              # optional: adds a cost estimate
      "spread_bps": 5.0, "fee_bps": 1.0, "sigma_daily_bps": 100.0, "coefficient": 0.1
    }

    # impact — cost a notional directly against a day's volume
    {
      "notional": 2000000.0, "adv": 50000000.0,
      "spread_bps": 5.0, "fee_bps": 1.0, "sigma_daily_bps": 100.0, "coefficient": 0.1
    }

    # ledger — record one decision into the trade log
    {
      "instrument": "AAPL", "side": "buy", "quantity": 100, "order_type": "market",
      "rationale": "...", "confidence": "high", "risk": "...", "falsify": "...",
      "reference_price": 192.0, "limit_price": null, "stop_price": null
    }
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from typing import Any, Optional

from .impact import estimate_cost
from .ledger import Decision, Ledger, load_ledger, save_ledger
from .orders import Order, OrderType, Side, TimeInForce, assess, validate_order


def _load(path: str) -> Any:
    raw = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(raw)


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _order_from_spec(spec: dict) -> Order:
    return Order(
        instrument=spec["instrument"],
        side=Side(spec.get("side", "buy").lower()),
        quantity=float(spec["quantity"]),
        order_type=OrderType(spec.get("order_type", "market").lower()),
        limit_price=float(spec["limit_price"]) if spec.get("limit_price") is not None else None,
        stop_price=float(spec["stop_price"]) if spec.get("stop_price") is not None else None,
        time_in_force=TimeInForce(spec.get("time_in_force", "day").lower()),
    )


def _order_dict(order: Order) -> dict:
    return {
        "instrument": order.instrument,
        "side": order.side.value,
        "quantity": order.quantity,
        "order_type": order.order_type.value,
        "limit_price": order.limit_price,
        "stop_price": order.stop_price,
        "time_in_force": order.time_in_force.value,
    }


def cmd_order(spec: dict) -> None:
    order = _order_from_spec(spec)
    validate_order(order)
    market_price = float(spec["market_price"]) if spec.get("market_price") is not None else None
    assessment = assess(order, market_price)

    out: dict = {
        "order": _order_dict(order),
        "marketable": assessment.marketable,
        "stop_wrong_side": assessment.stop_wrong_side,
        "warnings": assessment.warnings,
    }

    adv = spec.get("adv")
    if adv is not None:
        ref = order.limit_price if order.limit_price is not None else (
            order.stop_price if order.stop_price is not None else market_price
        )
        if ref is None:
            raise ValueError("cannot size notional: provide a limit/stop/market price")
        out["cost"] = asdict(estimate_cost(
            order.quantity * float(ref),
            float(adv),
            spread_bps=float(spec.get("spread_bps", 5.0)),
            fee_bps=float(spec.get("fee_bps", 1.0)),
            sigma_daily_bps=float(spec.get("sigma_daily_bps", 100.0)),
            coefficient=float(spec.get("coefficient", 0.1)),
        ))

    _emit(out)


def cmd_impact(spec: dict) -> None:
    _emit(asdict(estimate_cost(
        float(spec["notional"]),
        float(spec["adv"]),
        spread_bps=float(spec.get("spread_bps", 5.0)),
        fee_bps=float(spec.get("fee_bps", 1.0)),
        sigma_daily_bps=float(spec.get("sigma_daily_bps", 100.0)),
        coefficient=float(spec.get("coefficient", 0.1)),
    )))


def cmd_ledger(spec: dict, out_path: Optional[str]) -> None:
    decision = Decision(
        instrument=spec["instrument"],
        side=str(spec.get("side", "buy")).lower(),
        quantity=float(spec["quantity"]),
        order_type=str(spec.get("order_type", "market")).lower(),
        rationale=str(spec.get("rationale", "")),
        confidence=spec["confidence"],
        risk=str(spec.get("risk", "")),
        falsify=str(spec.get("falsify", "")),
        limit_price=float(spec["limit_price"]) if spec.get("limit_price") is not None else None,
        stop_price=float(spec["stop_price"]) if spec.get("stop_price") is not None else None,
        reference_price=float(spec["reference_price"]) if spec.get("reference_price") is not None else None,
        meta=spec.get("meta", {}),
    )
    if out_path and os.path.exists(out_path):
        ledger = load_ledger(out_path)
    else:
        ledger = Ledger()
    record = ledger.record(decision)
    if out_path:
        save_ledger(ledger, out_path)
    _emit(asdict(record))


def cmd_export(path: str) -> None:
    _emit(load_ledger(path).export())


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1nance.execution",
        description="F1NANCE execution & compliance layer (stdlib-only).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    order_p = sub.add_parser("order", help="validate + assess + cost an order")
    order_p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    impact_p = sub.add_parser("impact", help="estimate slippage + market impact")
    impact_p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    ledger_p = sub.add_parser("ledger", help="record a decision into the trade log")
    ledger_p.add_argument("spec", help="path to JSON spec, or '-' for stdin")
    ledger_p.add_argument("--out", help="path to persist the ledger (JSONL)")

    export_p = sub.add_parser("export", help="dump a persisted ledger as JSON")
    export_p.add_argument("path", help="path to a ledger JSONL file")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "order":
            cmd_order(_load(args.spec))
        elif args.cmd == "impact":
            cmd_impact(_load(args.spec))
        elif args.cmd == "ledger":
            cmd_ledger(_load(args.spec), args.out)
        elif args.cmd == "export":
            cmd_export(args.path)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
