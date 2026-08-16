"""Command-line entry point for the F1NANCE risk-management engine.

Run with::

    f1nance/.venv/bin/python -m f1nance.risk_management limits spec.json
    f1nance/.venv/bin/python -m f1nance.risk_management stress spec.json
    f1nance/.venv/bin/python -m f1nance.risk_management reverse_stress spec.json
    f1nance/.venv/bin/python -m f1nance.risk_management var_backtest spec.json

Emits JSON to stdout. Every command reads a JSON spec file (``-`` for stdin).

Spec shapes (returns are decimals; losses are positive magnitudes)::

    # limits — check named limits against current metric values
    {"limits": [
        {"name": "gross", "metric": "max_gross_exposure", "threshold": 1.5},
        {"name": "hhi", "metric": "hhi", "threshold": 0.25},
        {"name": "div", "metric": "effective_n", "threshold": 5, "direction": "min"}
     ],
     "metrics": {"max_gross_exposure": 1.8, "hhi": 0.30, "effective_n": 4}}

    # stress — linear factor shocks -> P&L (nav optional, enables pnl_pct)
    {"exposures": {"equity": 3000000, "rates": 1000000, "fx": -500000},
     "nav": 5000000,
     "scenarios": [
        {"name": "equity_crash", "shocks": {"equity": -0.30}},
        {"name": "rate_shock", "shocks": {"rates": 0.02}}
     ]}

    # reverse_stress — solve the shock that produces a target loss
    {"exposures": {"equity": 3000000}, "factor": "equity", "target_loss": 600000}

    # var_backtest — Kupiec POF + Christoffersen independence
    {"var_forecasts": [0.02, 0.02, ...], "realized_returns": [-0.01, 0.03, ...],
     "confidence": 0.95, "significance": 0.05}
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, Optional

from .backtest import var_backtest
from .limits import Limit, check_limits
from .stress import Scenario, reverse_stress, stress_test


def _load(path: str) -> Any:
    raw = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(raw)


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _exposures(spec: dict) -> dict:
    return {str(k): float(v) for k, v in spec["exposures"].items()}


def cmd_limits(spec: dict) -> None:
    limits = [Limit(**l) for l in spec["limits"]]
    metrics = {str(k): float(v) for k, v in spec["metrics"].items()}
    _emit(asdict(check_limits(limits, metrics)))


def cmd_stress(spec: dict) -> None:
    nav = spec.get("nav")
    outcomes = stress_test(
        _exposures(spec),
        [Scenario(**s) for s in spec["scenarios"]],
        nav=float(nav) if nav is not None else None,
    )
    _emit({"nav": nav, "scenarios": [asdict(o) for o in outcomes]})


def cmd_reverse_stress(spec: dict) -> None:
    _emit(
        asdict(
            reverse_stress(
                _exposures(spec),
                str(spec["factor"]),
                float(spec["target_loss"]),
            )
        )
    )


def cmd_var_backtest(spec: dict) -> None:
    _emit(
        asdict(
            var_backtest(
                [float(v) for v in spec["var_forecasts"]],
                [float(r) for r in spec["realized_returns"]],
                confidence=float(spec.get("confidence", 0.95)),
                significance=float(spec.get("significance", 0.05)),
            )
        )
    )


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1nance.risk_management",
        description="F1NANCE risk-management engine (stdlib-only).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name, help_ in (
        ("limits", "check risk limits against current metrics"),
        ("stress", "scenario stress test (factor shocks -> P&L)"),
        ("reverse_stress", "solve the shock that produces a target loss"),
        ("var_backtest", "Kupiec + Christoffersen VaR backtest"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    args = parser.parse_args(argv)
    try:
        spec = _load(args.spec)
        handlers = {
            "limits": cmd_limits,
            "stress": cmd_stress,
            "reverse_stress": cmd_reverse_stress,
            "var_backtest": cmd_var_backtest,
        }
        handlers[args.cmd](spec)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
