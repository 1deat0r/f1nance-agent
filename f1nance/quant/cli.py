"""Command-line entry point for the F1NANCE quant & backtesting engine.

Run with::

    f1nance/.venv/bin/python -m f1nance.quant capm spec.json
    f1nance/.venv/bin/python -m f1nance.quant ff spec.json
    f1nance/.venv/bin/python -m f1nance.quant backtest spec.json
    f1nance/.venv/bin/python -m f1nance.quant momentum spec.json

Emits JSON to stdout. Every command reads a JSON spec file (``-`` for stdin).

Spec shapes::

    # capm — single-factor regression
    {
      "asset_returns": [0.02, -0.01, 0.03, ...],
      "market_returns": [0.01, 0.00, 0.02, ...],
      "risk_free_rate": 0.0, "periods_per_year": 252
    }

    # ff — multi-factor regression (factor names are keys)
    {
      "asset_returns": [...],
      "factors": {"MKT": [...], "SMB": [...], "HML": [...]},
      "risk_free_rate": 0.0, "periods_per_year": 252
    }

    # backtest — a supplied sequence of target weights
    {
      "returns": {"A": [...], "B": [...]},
      "weights": [{"A": 0.6, "B": 0.4}, ...],
      "cost_bps": 2.0, "slippage_bps": 1.0, "periods_per_year": 252
    }

    # momentum — a real walk-forward demo (top_k by trailing return)
    {
      "returns": {"A": [...], "B": [...]},
      "lookback": 5, "top_k": 1, "min_train": 10,
      "window": null, "cost_bps": 2.0, "slippage_bps": 1.0, "periods_per_year": 252
    }

``momentum`` reports the out-of-sample record and the leaky in-sample baseline
side by side (``in_sample.lookahead`` is ``true``).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, Optional

from .backtest import backtest_weights, walk_forward
from .factors import capm, momentum_predictor, multi_factor


def _load(path: str) -> Any:
    raw = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(raw)


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_capm(spec: dict) -> None:
    result = capm(
        [float(r) for r in spec["asset_returns"]],
        [float(r) for r in spec["market_returns"]],
        risk_free_rate=float(spec.get("risk_free_rate", 0.0)),
        periods_per_year=int(spec.get("periods_per_year", 252)),
    )
    _emit(asdict(result))


def cmd_ff(spec: dict) -> None:
    factors: dict = {name: [float(r) for r in series] for name, series in spec["factors"].items()}
    result = multi_factor(
        [float(r) for r in spec["asset_returns"]],
        factors,
        risk_free_rate=float(spec.get("risk_free_rate", 0.0)),
        periods_per_year=int(spec.get("periods_per_year", 252)),
    )
    _emit(asdict(result))


def cmd_backtest(spec: dict) -> None:
    returns = {a: [float(r) for r in series] for a, series in spec["returns"].items()}
    weights = spec["weights"]
    result = backtest_weights(
        weights,
        returns,
        cost_bps=float(spec.get("cost_bps", 0.0)),
        slippage_bps=float(spec.get("slippage_bps", 0.0)),
        periods_per_year=int(spec.get("periods_per_year", 252)),
    )
    _emit(asdict(result))


def cmd_momentum(spec: dict) -> None:
    returns = {a: [float(r) for r in series] for a, series in spec["returns"].items()}
    lookback = int(spec["lookback"])
    top_k = int(spec["top_k"])
    min_train = int(spec["min_train"])
    window = spec.get("window")
    result = walk_forward(
        returns,
        momentum_predictor(lookback, top_k),
        min_train=min_train,
        window=int(window) if window is not None else None,
        cost_bps=float(spec.get("cost_bps", 0.0)),
        slippage_bps=float(spec.get("slippage_bps", 0.0)),
        periods_per_year=int(spec.get("periods_per_year", 252)),
    )
    _emit(asdict(result))


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1nance.quant",
        description="F1NANCE quant & backtesting engine (stdlib-only).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    capm_p = sub.add_parser("capm", help="single-factor CAPM regression")
    capm_p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    ff_p = sub.add_parser("ff", help="multi-factor (Fama-French/Carhart) regression")
    ff_p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    bt_p = sub.add_parser("backtest", help="backtest a sequence of target weights")
    bt_p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    mom_p = sub.add_parser("momentum", help="walk-forward momentum demo (OOS vs in-sample)")
    mom_p.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    args = parser.parse_args(argv)
    try:
        spec = _load(args.spec)
        if args.cmd == "capm":
            cmd_capm(spec)
        elif args.cmd == "ff":
            cmd_ff(spec)
        elif args.cmd == "backtest":
            cmd_backtest(spec)
        elif args.cmd == "momentum":
            cmd_momentum(spec)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
