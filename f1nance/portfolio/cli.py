"""Command-line entry point for the F1NANCE portfolio & risk engine.

Run with::

    f1nance/.venv/bin/python -m f1nance.portfolio value spec.json
    f1nance/.venv/bin/python -m f1nance.portfolio risk prices.json
    f1nance/.venv/bin/python -m f1nance.portfolio attr spec.json

Emits JSON to stdout. ``value`` and ``attr`` read a JSON spec file (``-`` for
stdin); ``risk`` reads a JSON list of prices or ``{"prices": [...]}``.

Spec shapes::

    # value
    {
      "base_currency": "USD", "fx_rates": {"EUR": 1.09},
      "cash": {"USD": 10000},
      "positions": [
        {"asset": "AAPL", "quantity": 100, "price": 210.0,
         "currency": "USD", "asset_class": "equity", "cost_basis": 180.0}
      ]
    }

    # attr
    {
      "portfolio_weights": {"A": 0.6, "B": 0.4},
      "benchmark_weights": {"A": 0.5, "B": 0.5},
      "portfolio_returns": {"A": 0.10, "B": 0.05},
      "benchmark_returns": {"A": 0.08, "B": 0.06}
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional

from .attribution import brinson
from .positions import InvalidPortfolio, MissingFxRate, Portfolio, Position, rebalance_trades
from .risk import (
    annualized_return,
    annualized_volatility,
    cvar_historical,
    max_drawdown,
    returns_from_prices,
    sharpe_ratio,
    sortino_ratio,
    var_historical,
)


def _load(path: str) -> Any:
    raw = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(raw)


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _portfolio_from_spec(spec: dict) -> Portfolio:
    positions = [Position(**p) for p in spec.get("positions", [])]
    return Portfolio(
        positions=positions,
        cash=spec.get("cash", {}),
        base_currency=spec.get("base_currency", "USD"),
        fx_rates=spec.get("fx_rates", {}),
    )


def cmd_value(spec: dict) -> None:
    port = _portfolio_from_spec(spec)
    nav = port.market_value(include_cash=True)
    exposure = port.exposure()
    holdings = [h.__dict__ for h in port.holdings(include_cash=True)]
    cash_w = port.cash_weight()
    out = {
        "nav": nav,
        "cash_weight": cash_w,
        "exposure": exposure.__dict__,
        "exposure_by_class": port.exposure_by_class(),
        "holdings": holdings,
    }
    drag_asset_return = spec.get("cash_drag_asset_return")
    if drag_asset_return is not None:
        out["cash_drag"] = port.cash_drag(drag_asset_return)
    target = spec.get("target_weights")
    if target is not None:
        out["rebalance_trades"] = rebalance_trades(port.position_base_values(), target, total_value=nav)
    _emit(out)


def cmd_risk(raw: Any) -> None:
    if isinstance(raw, dict):
        prices = raw.get("prices", raw.get("closes"))
    else:
        prices = raw
    if prices is None:
        raise ValueError("risk input must be a list of prices or {'prices': [...]}")
    method = "log" if (isinstance(raw, dict) and raw.get("log_returns")) else "simple"
    rets = returns_from_prices([float(p) for p in prices], method=method)
    periods = int((raw.get("periods_per_year") if isinstance(raw, dict) else None) or 252)
    out = {
        "observations": len(prices),
        "returns": len(rets),
        "annualized_return": None,
        "annualized_volatility": annualized_volatility(rets, periods),
        "sharpe_ratio": None,
        "sortino_ratio": None,
        "var_historical_95": var_historical(rets, 0.95),
        "cvar_historical_95": cvar_historical(rets, 0.95),
        "max_drawdown": max_drawdown(prices),
    }
    try:
        out["annualized_return"] = annualized_return(rets, periods, geometric=True)
    except ValueError:
        pass
    try:
        out["sharpe_ratio"] = sharpe_ratio(rets, 0.0, periods)
    except ValueError:
        pass
    try:
        out["sortino_ratio"] = sortino_ratio(rets, 0.0, periods)
    except ValueError:
        pass
    _emit(out)


def cmd_attr(spec: dict) -> None:
    result = brinson(
        spec.get("portfolio_weights", {}),
        spec.get("benchmark_weights", {}),
        spec.get("portfolio_returns", {}),
        spec.get("benchmark_returns", {}),
    )
    _emit({
        "portfolio_return": result.portfolio_return,
        "benchmark_return": result.benchmark_return,
        "active_return": result.active_return,
        "allocation": result.allocation_total,
        "selection": result.selection_total,
        "interaction": result.interaction_total,
        "rows": [r.__dict__ for r in result.rows],
    })


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1nance.portfolio",
        description="F1NANCE portfolio & risk engine (stdlib-only).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    value = sub.add_parser("value", help="NAV, weights, exposure from a portfolio spec")
    value.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    risk = sub.add_parser("risk", help="risk metrics from a price series")
    risk.add_argument("prices", help="JSON list of prices, or {'prices': [...]}")

    attr = sub.add_parser("attr", help="Brinson attribution from a spec")
    attr.add_argument("spec", help="path to JSON spec, or '-' for stdin")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "value":
            cmd_value(_load(args.spec))
        elif args.cmd == "risk":
            cmd_risk(_load(args.prices))
        elif args.cmd == "attr":
            cmd_attr(_load(args.spec))
    except (ValueError, InvalidPortfolio, MissingFxRate, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
