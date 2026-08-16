"""The agent's tool registry — the finance engines as callable tools.

Phase 6 turns F1NANCE from a set of engine CLIs into an agent by exposing each
engine as a *tool* the model can call with structured arguments. A :class:`Tool`
is a name, a JSON-schema parameter shape, and a handler that returns a JSON
string. The :class:`ToolRegistry` collects them, emits their schemas, and
dispatches calls — catching handler errors and returning an honest
``{"error": ...}`` result rather than letting one bad call crash the loop.

Hermes-independent: handlers call the ``f1nance`` engines directly (stdlib
only). The data handlers reach the network only when the cache is stale; the
portfolio/quant/execution handlers are pure computation; the desk handler uses
an injected executor (a live model call by default, scripted in tests); the
memory handlers write the provenance store.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from ..core.memory import MemoryStore
from ..data import (
    get_company_facts,
    get_filings,
    get_macro_series,
    get_price_history,
)
from ..desk import Brief, Desk
from ..desk.live import env_client, model_executor
from ..execution.impact import estimate_cost
from ..execution.ledger import Decision, Ledger, load_ledger, save_ledger
from ..execution.orders import Order, OrderType, Side, TimeInForce, assess, validate_order
from ..portfolio.attribution import brinson
from ..portfolio.positions import Position, Portfolio, rebalance_trades
from ..portfolio.risk import (
    annualized_return,
    annualized_volatility,
    cvar_historical,
    max_drawdown,
    returns_from_prices,
    sharpe_ratio,
    sortino_ratio,
    var_historical,
)
from ..fixed_income import (
    bond_price,
    bootstrap_spot_curve,
    duration_and_convexity,
    forward_rate,
    interpolate_spot,
    pv,
    pv_curve,
    ytm,
)
from ..deal_memo import build_deal_memo
from ..derivatives import black_scholes, binomial_price, greeks, implied_volatility
from ..risk_management import (
    Limit,
    Scenario,
    check_limits,
    reverse_stress,
    stress_test,
    var_backtest,
)
from ..m_and_a import accretion_dilution, lbo, synergy_breakeven, synergy_value
from ..quant.backtest import backtest_weights, walk_forward
from ..quant.factors import capm, momentum_predictor, multi_factor
from .paths import default_store_path


def _json(obj: Any) -> str:
    return json.dumps(obj, default=str)


# -- data summary helpers -----------------------------------------------------

def _bars_summary(bars: list, edge: int = 5) -> dict:
    """A bounded view of a bar series: count + first/last ``edge`` bars."""
    if not bars:
        return {"count": 0, "bars": []}
    return {"count": len(bars), "first": bars[:edge], "last": bars[-edge:]}


def _obs_summary(observations: list, tail: int = 12) -> dict:
    """A bounded view of a macro series: count + the latest ``tail`` points."""
    if not observations:
        return {"count": 0, "observations": []}
    return {"count": len(observations), "latest": observations[-tail:]}


def _verdict_dict(v) -> dict:
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


# -- portfolio / execution plumbing (mirrors the CLIs) -----------------------

def _portfolio_from_spec(spec: dict) -> Portfolio:
    positions = [Position(**p) for p in spec.get("positions", [])]
    return Portfolio(
        positions=positions,
        cash=spec.get("cash", {}),
        base_currency=spec.get("base_currency", "USD"),
        fx_rates=spec.get("fx_rates", {}),
    )


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


# -- engine-backed handlers (pure computation or cached network) --------------

def h_market_price(args: dict) -> str:
    symbol = str(args["symbol"]).strip().upper()
    ds = get_price_history(
        symbol,
        period=str(args.get("period", "5y")),
        interval=str(args.get("interval", "1d")),
        refresh=bool(args.get("refresh", False)),
    )
    return _json(
        {
            "symbol": symbol,
            "source": ds.source,
            "as_of": ds.as_of,
            "degraded": ds.degraded,
            "cached": ds.cached,
            "bars": _bars_summary(ds.data.get("bars", [])),
        }
    )


def h_market_macro(args: dict) -> str:
    series_id = str(args["series_id"]).strip().upper()
    ds = get_macro_series(series_id)
    return _json(
        {
            "series_id": series_id,
            "source": ds.source,
            "as_of": ds.as_of,
            "cached": ds.cached,
            "observations": _obs_summary(ds.data.get("observations", [])),
        }
    )


def h_market_facts(args: dict) -> str:
    ds = get_company_facts(str(args["cik"]))
    facts = ds.data.get("facts", {})
    tags: list = []
    if isinstance(facts, dict):
        for namespace, tag_map in facts.items():
            if isinstance(tag_map, dict):
                tags.extend(f"{namespace}:{tag}" for tag in tag_map)
    tags.sort()
    return _json(
        {
            "cik": ds.data.get("cik"),
            "source": ds.source,
            "tag_count": len(tags),
            "tags": tags[:200],
        }
    )


def h_market_filings(args: dict) -> str:
    ds = get_filings(str(args["cik"]))
    subs = ds.data.get("submissions", {}) or {}
    recent = subs.get("recent", {}) or {}
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    n = min(20, len(forms))
    filings = [
        {
            "form": forms[i],
            "filing_date": dates[i] if i < len(dates) else None,
            "accession": accessions[i] if i < len(accessions) else None,
        }
        for i in range(n)
    ]
    return _json(
        {
            "cik": ds.data.get("cik"),
            "source": ds.source,
            "name": subs.get("name"),
            "recent_filings": filings,
        }
    )


def h_portfolio_value(args: dict) -> str:
    spec = args["spec"]
    port = _portfolio_from_spec(spec)
    nav = port.market_value(include_cash=True)
    out: dict = {
        "nav": nav,
        "cash_weight": port.cash_weight(),
        "exposure": port.exposure().__dict__,
        "exposure_by_class": port.exposure_by_class(),
        "holdings": [h.__dict__ for h in port.holdings(include_cash=True)],
    }
    if spec.get("cash_drag_asset_return") is not None:
        out["cash_drag"] = port.cash_drag(float(spec["cash_drag_asset_return"]))
    if spec.get("target_weights") is not None:
        out["rebalance_trades"] = rebalance_trades(
            port.position_base_values(), spec["target_weights"], total_value=nav
        )
    return _json(out)


def h_portfolio_risk(args: dict) -> str:
    prices = args.get("prices")
    if not isinstance(prices, list) or not prices:
        raise ValueError("risk requires a non-empty 'prices' list of numbers")
    method = "log" if args.get("log_returns") else "simple"
    rets = returns_from_prices([float(p) for p in prices], method=method)
    periods = int(args.get("periods_per_year", 252))
    out: dict = {
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
    for key, fn in (
        ("annualized_return", lambda: annualized_return(rets, periods, geometric=True)),
        ("sharpe_ratio", lambda: sharpe_ratio(rets, 0.0, periods)),
        ("sortino_ratio", lambda: sortino_ratio(rets, 0.0, periods)),
    ):
        try:
            out[key] = fn()
        except ValueError:
            pass
    return _json(out)


def h_portfolio_attribution(args: dict) -> str:
    spec = args["spec"]
    result = brinson(
        spec.get("portfolio_weights", {}),
        spec.get("benchmark_weights", {}),
        spec.get("portfolio_returns", {}),
        spec.get("benchmark_returns", {}),
    )
    return _json(
        {
            "portfolio_return": result.portfolio_return,
            "benchmark_return": result.benchmark_return,
            "active_return": result.active_return,
            "allocation": result.allocation_total,
            "selection": result.selection_total,
            "interaction": result.interaction_total,
            "rows": [r.__dict__ for r in result.rows],
        }
    )


def h_quant_capm(args: dict) -> str:
    result = capm(
        [float(r) for r in args["asset_returns"]],
        [float(r) for r in args["market_returns"]],
        risk_free_rate=float(args.get("risk_free_rate", 0.0)),
        periods_per_year=int(args.get("periods_per_year", 252)),
    )
    return _json(asdict(result))


def h_quant_ff(args: dict) -> str:
    factors: dict = {
        name: [float(r) for r in series]
        for name, series in args["factors"].items()
    }
    result = multi_factor(
        [float(r) for r in args["asset_returns"]],
        factors,
        risk_free_rate=float(args.get("risk_free_rate", 0.0)),
        periods_per_year=int(args.get("periods_per_year", 252)),
    )
    return _json(asdict(result))


def h_quant_backtest(args: dict) -> str:
    spec = args["spec"]
    returns = {a: [float(r) for r in series] for a, series in spec["returns"].items()}
    result = backtest_weights(
        spec["weights"],
        returns,
        cost_bps=float(spec.get("cost_bps", 0.0)),
        slippage_bps=float(spec.get("slippage_bps", 0.0)),
        periods_per_year=int(spec.get("periods_per_year", 252)),
    )
    return _json(asdict(result))


def h_quant_momentum(args: dict) -> str:
    returns = {a: [float(r) for r in series] for a, series in args["returns"].items()}
    window = args.get("window")
    result = walk_forward(
        returns,
        momentum_predictor(int(args["lookback"]), int(args["top_k"])),
        min_train=int(args["min_train"]),
        window=int(window) if window is not None else None,
        cost_bps=float(args.get("cost_bps", 0.0)),
        slippage_bps=float(args.get("slippage_bps", 0.0)),
        periods_per_year=int(args.get("periods_per_year", 252)),
    )
    return _json(asdict(result))


def h_execution_order(args: dict) -> str:
    spec = args["spec"]
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
        out["cost"] = asdict(
            estimate_cost(
                order.quantity * float(ref),
                float(adv),
                spread_bps=float(spec.get("spread_bps", 5.0)),
                fee_bps=float(spec.get("fee_bps", 1.0)),
                sigma_daily_bps=float(spec.get("sigma_daily_bps", 100.0)),
                coefficient=float(spec.get("coefficient", 0.1)),
            )
        )
    return _json(out)


def h_execution_impact(args: dict) -> str:
    return _json(
        asdict(
            estimate_cost(
                float(args["notional"]),
                float(args["adv"]),
                spread_bps=float(args.get("spread_bps", 5.0)),
                fee_bps=float(args.get("fee_bps", 1.0)),
                sigma_daily_bps=float(args.get("sigma_daily_bps", 100.0)),
                coefficient=float(args.get("coefficient", 0.1)),
            )
        )
    )


# -- fixed income ------------------------------------------------------------

def h_fixedincome_price(args: dict) -> str:
    return _json(
        {
            "price": bond_price(
                float(args.get("coupon_rate", 0.0)),
                float(args["maturity_years"]),
                float(args["ytm"]),
                face=float(args.get("face", 100.0)),
                payments_per_year=int(args.get("payments_per_year", 2)),
            )
        }
    )


def h_fixedincome_ytm(args: dict) -> str:
    return _json(
        {
            "ytm": ytm(
                float(args["price"]),
                float(args.get("coupon_rate", 0.0)),
                float(args["maturity_years"]),
                face=float(args.get("face", 100.0)),
                payments_per_year=int(args.get("payments_per_year", 2)),
            )
        }
    )


def h_fixedincome_risk(args: dict) -> str:
    return _json(
        asdict(
            duration_and_convexity(
                float(args.get("coupon_rate", 0.0)),
                float(args["maturity_years"]),
                float(args["ytm"]),
                face=float(args.get("face", 100.0)),
                payments_per_year=int(args.get("payments_per_year", 2)),
            )
        )
    )


def h_fixedincome_curve(args: dict) -> str:
    spec = args["spec"]
    if "par_tenors" in spec:
        tenors, spots = bootstrap_spot_curve(
            [float(t) for t in spec["par_tenors"]],
            [float(y) for y in spec["par_yields"]],
        )
        return _json({"tenors": tenors, "spots": spots})
    if "rate_t1" in spec:
        return _json(
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
    if "cashflows" in spec:
        cfs = [float(c) for c in spec["cashflows"]]
        ts = [float(t) for t in spec["times"]]
        if "tenors" in spec:
            return _json(
                {
                    "pv": pv_curve(
                        cfs,
                        ts,
                        [float(t) for t in spec["tenors"]],
                        [float(s) for s in spec["spots"]],
                        compounding=spec.get("compounding", 2),
                    )
                }
            )
        return _json(
            {"pv": pv(cfs, ts, float(spec["rate"]), compounding=spec.get("compounding", 2))}
        )
    if "tenors" in spec and "t" in spec:
        return _json(
            {
                "spot": interpolate_spot(
                    [float(t) for t in spec["tenors"]],
                    [float(s) for s in spec["spots"]],
                    float(spec["t"]),
                )
            }
        )
    raise ValueError(
        "curve spec needs par_tenors/par_yields, rate_t1/rate_t2, "
        "tenors/spots/t, or cashflows/times"
    )


# -- derivatives -------------------------------------------------------------

def h_derivatives_price(args: dict) -> str:
    result = black_scholes(
        str(args["call_put"]),
        float(args["S"]),
        float(args["K"]),
        float(args["T"]),
        float(args.get("r", 0.0)),
        float(args["sigma"]),
        q=float(args.get("q", 0.0)),
    )
    return _json({"call_put": str(args["call_put"]).lower(), **asdict(result)})


def h_derivatives_greeks(args: dict) -> str:
    result = greeks(
        str(args["call_put"]),
        float(args["S"]),
        float(args["K"]),
        float(args["T"]),
        float(args.get("r", 0.0)),
        float(args["sigma"]),
        q=float(args.get("q", 0.0)),
    )
    return _json({"call_put": str(args["call_put"]).lower(), **asdict(result)})


def h_derivatives_implied_vol(args: dict) -> str:
    return _json(
        {
            "implied_volatility": implied_volatility(
                float(args["price"]),
                str(args["call_put"]),
                float(args["S"]),
                float(args["K"]),
                float(args["T"]),
                float(args.get("r", 0.0)),
                q=float(args.get("q", 0.0)),
            )
        }
    )


def h_derivatives_binomial(args: dict) -> str:
    return _json(
        {
            "call_put": str(args["call_put"]).lower(),
            "price": binomial_price(
                str(args["call_put"]),
                float(args["S"]),
                float(args["K"]),
                float(args["T"]),
                float(args.get("r", 0.0)),
                float(args["sigma"]),
                q=float(args.get("q", 0.0)),
                steps=int(args.get("steps", 200)),
                american=bool(args.get("american", False)),
            ),
            "steps": int(args.get("steps", 200)),
            "american": bool(args.get("american", False)),
        }
    )


# -- risk management ---------------------------------------------------------

def _exposures(spec: dict) -> dict:
    return {str(k): float(v) for k, v in spec["exposures"].items()}


def h_riskmanagement_limits(args: dict) -> str:
    spec = args["spec"]
    limits = [Limit(**l) for l in spec["limits"]]
    metrics = {str(k): float(v) for k, v in spec["metrics"].items()}
    return _json(asdict(check_limits(limits, metrics)))


def h_riskmanagement_stress(args: dict) -> str:
    spec = args["spec"]
    nav = float(spec["nav"]) if spec.get("nav") is not None else None
    outcomes = stress_test(
        _exposures(spec),
        [Scenario(**s) for s in spec["scenarios"]],
        nav=nav,
    )
    return _json({"nav": nav, "scenarios": [asdict(o) for o in outcomes]})


def h_riskmanagement_reverse_stress(args: dict) -> str:
    spec = args["spec"]
    return _json(
        asdict(
            reverse_stress(
                _exposures(spec),
                str(spec["factor"]),
                float(spec["target_loss"]),
            )
        )
    )


def h_riskmanagement_var_backtest(args: dict) -> str:
    result = var_backtest(
        [float(v) for v in args["var_forecasts"]],
        [float(r) for r in args["realized_returns"]],
        confidence=float(args.get("confidence", 0.95)),
        significance=float(args.get("significance", 0.05)),
    )
    return _json(asdict(result))


# -- m-and-a -----------------------------------------------------------------

def h_manda_accretion(args: dict) -> str:
    result = accretion_dilution(
        float(args.get("acquirer_ni", 0.0)),
        float(args["acquirer_shares"]),
        float(args.get("target_ni", 0.0)),
        float(args["purchase_price"]),
        float(args["cash_portion"]),
        float(args["stock_portion"]),
        float(args.get("acquirer_share_price", 0.0)),
        float(args["tax_rate"]),
        cost_synergies=float(args.get("cost_synergies", 0.0)),
        revenue_synergies=float(args.get("revenue_synergies", 0.0)),
        new_debt_rate=float(args.get("new_debt_rate", 0.0)),
        cash_used=float(args.get("cash_used", 0.0)),
        cash_yield=float(args.get("cash_yield", 0.0)),
    )
    return _json(asdict(result))


def h_manda_synergies(args: dict) -> str:
    result = synergy_value(
        float(args.get("cost_synergies", 0.0)),
        float(args.get("revenue_synergies", 0.0)),
        float(args.get("revenue_margin", 0.0)),
        float(args["tax_rate"]),
        float(args["discount_rate"]),
        int(args["ramp_years"]),
        float(args.get("integration_costs", 0.0)),
        float(args["premium_paid"]),
        growth=float(args.get("growth", 0.0)),
    )
    return _json(asdict(result))


def h_manda_breakeven(args: dict) -> str:
    result = synergy_breakeven(
        float(args["premium_paid"]),
        float(args.get("integration_costs", 0.0)),
        float(args["tax_rate"]),
        float(args["discount_rate"]),
        int(args["ramp_years"]),
        growth=float(args.get("growth", 0.0)),
    )
    return _json(asdict(result))


def h_manda_lbo(args: dict) -> str:
    result = lbo(
        float(args["enterprise_value"]),
        float(args.get("existing_net_debt", 0.0)),
        float(args.get("fees", 0.0)),
        float(args["entry_debt"]),
        float(args["ebitda_0"]),
        float(args["ebitda_growth"]),
        int(args["years"]),
        float(args["fcf_margin"]),
        float(args["exit_multiple"]),
        float(args["interest_rate"]),
        tax_rate=float(args.get("tax_rate", 0.0)),
    )
    return _json(asdict(result))


# -- deal memo ----------------------------------------------------------------

def h_dealmemo_run(args: dict) -> str:
    memo = build_deal_memo(args["spec"])
    return _json(asdict(memo))


# -- the registry ------------------------------------------------------------

@dataclass(frozen=True)
class Tool:
    """A callable tool: name, description, JSON-schema parameters, handler."""

    name: str
    description: str
    parameters: dict
    handler: Callable[[dict], str]

    def schema(self) -> dict:
        """The OpenAI function-tool schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """A name → Tool map that emits schemas and dispatches calls.

    ``dispatch`` never raises: a missing tool or a failing handler is returned
    as an honest ``{"error": ...}`` JSON string so the agent loop can report
    the blocker and adapt, rather than crashing on one bad call.
    """

    def __init__(self, tools: list):
        self.tools = {t.name: t for t in tools}

    def schemas(self) -> list:
        return [t.schema() for t in self.tools.values()]

    def names(self) -> list:
        return list(self.tools)

    def dispatch(self, name: str, arguments: Optional[dict]) -> str:
        tool = self.tools.get(name)
        if tool is None:
            return _json({"error": f"unknown tool {name!r}"})
        try:
            return tool.handler(dict(arguments or {}))
        except Exception as exc:  # noqa: BLE001 — surface any handler failure honestly
            return _json({"error": f"{type(exc).__name__}: {exc}"})


def _obj(description: str) -> dict:
    """A free-form JSON object parameter documented by its description."""
    return {"type": "object", "description": description}


def _scalar_params(required: list, properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _spec_param(description: str) -> dict:
    """The standard 'spec' parameter used by the engine tools."""
    return _scalar_params(["spec"], {"spec": _obj(description)})


def build_registry(
    store: Optional[MemoryStore] = None,
    desk_executor: Optional[Callable] = None,
    ledger_path: Optional[str] = None,
) -> ToolRegistry:
    """Build the full tool registry.

    ``store`` defaults to the canonical provenance store (override with
    ``F1NANCE_STORE`` or pass a ``MemoryStore`` / path). ``desk_executor`` is
    the desk's ``(Seat, Brief) -> Finding`` callable; when omitted, the desk
    tool lazily builds a live model executor from the environment on first use.
    ``ledger_path`` is where the execution ledger persists (default: in-memory
    only; set ``F1NANCE_LEDGER`` or pass a path to persist).
    """
    if store is None:
        store = MemoryStore(default_store_path())
    elif isinstance(store, (str, Path)):
        store = MemoryStore(store)
    ledger_path = ledger_path if ledger_path is not None else os.environ.get("F1NANCE_LEDGER")

    def h_memory_record(args: dict) -> str:
        with store.mutate():
            fact = store.add(
                content=str(args.get("content", "")),
                kind=str(args.get("kind", "memory")),
                source=str(args.get("source", "foreground")),
                supersedes=list(args.get("supersedes", [])),
                note=str(args.get("note", "")),
            )
        return _json(asdict(fact))

    def h_memory_export(args: dict) -> str:
        return _json(store.export())

    def h_memory_retract(args: dict) -> str:
        with store.mutate():
            fact = store.retract(str(args["fact_id"]), source="agent")
        return _json(asdict(fact) if fact is not None else None)

    def h_execution_ledger(args: dict) -> str:
        spec = args["spec"]
        decision = Decision(
            instrument=spec["instrument"],
            side=str(spec.get("side", "buy")).lower(),
            quantity=float(spec["quantity"]),
            order_type=str(spec.get("order_type", "market")).lower(),
            rationale=str(spec.get("rationale", "")),
            confidence=spec.get("confidence", "medium"),
            risk=str(spec.get("risk", "")),
            falsify=str(spec.get("falsify", "")),
            limit_price=float(spec["limit_price"]) if spec.get("limit_price") is not None else None,
            stop_price=float(spec["stop_price"]) if spec.get("stop_price") is not None else None,
            reference_price=float(spec["reference_price"]) if spec.get("reference_price") is not None else None,
            meta=spec.get("meta", {}),
        )
        ledger = load_ledger(ledger_path) if (ledger_path and os.path.exists(ledger_path)) else Ledger()
        record = ledger.record(decision)
        if ledger_path:
            save_ledger(ledger, ledger_path)
        return _json(asdict(record))

    def h_desk(args: dict) -> str:
        brief = Brief(
            objective=str(args.get("objective", "")),
            context=str(args.get("context", "")),
            horizon=str(args.get("horizon", "")),
            risk_capacity=str(args.get("risk_capacity", "")),
            constraints=tuple(args.get("constraints", ())),
            seats=tuple(args.get("seats", ())),
        )
        executor = desk_executor if desk_executor is not None else model_executor(env_client())
        verdict = Desk().run(brief, executor)
        return _json(_verdict_dict(verdict))

    tools = [
        # market data
        Tool(
            "market_price",
            "Fetch daily or intraday OHLCV price history for an equity ticker "
            "(yfinance, falling back to stooq). Returns provenance (source, "
            "as-of, degraded, cached) plus a bounded summary of the bars.",
            _scalar_params(
                ["symbol"],
                {
                    "symbol": {"type": "string", "description": "Ticker, e.g. AAPL"},
                    "period": {"type": "string", "description": "e.g. 1mo, 1y, 5y (default 5y)"},
                    "interval": {"type": "string", "description": "1d (default) or intraday e.g. 1h"},
                },
            ),
            h_market_price,
        ),
        Tool(
            "market_macro",
            "Fetch a FRED macroeconomic series by id (e.g. CPIAUCSL, DFF, GDP).",
            _scalar_params(
                ["series_id"],
                {"series_id": {"type": "string", "description": "FRED series id"}},
            ),
            h_market_macro,
        ),
        Tool(
            "market_facts",
            "Fetch SEC XBRL company facts (structured fundamentals) by CIK.",
            _scalar_params(
                ["cik"],
                {"cik": {"type": "string", "description": "SEC CIK number, e.g. 320193"}},
            ),
            h_market_facts,
        ),
        Tool(
            "market_filings",
            "Fetch SEC filing history (submissions) for a company by CIK.",
            _scalar_params(
                ["cik"],
                {"cik": {"type": "string", "description": "SEC CIK number, e.g. 320193"}},
            ),
            h_market_filings,
        ),
        # portfolio & risk
        Tool(
            "portfolio_value",
            "Compute NAV, weights, exposure, cash drag, and rebalance trades "
            "from a portfolio spec.",
            _spec_param(
                "Portfolio spec: {base_currency, fx_rates, cash: {CCY: amount}, "
                "positions: [{asset, quantity, price, currency, asset_class, "
                "cost_bias}], optional cash_drag_asset_return, optional target_weights}."
            ),
            h_portfolio_value,
        ),
        Tool(
            "portfolio_risk",
            "Compute risk metrics (vol, Sharpe/Sortino, VaR/CVaR, max drawdown) "
            "from a price series.",
            _scalar_params(
                ["prices"],
                {
                    "prices": {"type": "array", "items": {"type": "number"}, "description": "Close price series"},
                    "periods_per_year": {"type": "integer", "description": "Default 252"},
                    "log_returns": {"type": "boolean", "description": "Use log returns (default simple)"},
                },
            ),
            h_portfolio_risk,
        ),
        Tool(
            "portfolio_attribution",
            "Brinson-Fachler performance attribution (allocation/selection/"
            "interaction) from weights and returns.",
            _spec_param(
                "Attribution spec: {portfolio_weights, benchmark_weights, "
                "portfolio_returns, benchmark_returns} — all maps of asset -> number."
            ),
            h_portfolio_attribution,
        ),
        # quant & backtesting
        Tool(
            "quant_capm",
            "Single-factor CAPM regression (alpha, beta, t-stats, R²).",
            _scalar_params(
                ["asset_returns", "market_returns"],
                {
                    "asset_returns": {"type": "array", "items": {"type": "number"}},
                    "market_returns": {"type": "array", "items": {"type": "number"}},
                    "risk_free_rate": {"type": "number", "description": "Default 0.0"},
                    "periods_per_year": {"type": "integer", "description": "Default 252"},
                },
            ),
            h_quant_capm,
        ),
        Tool(
            "quant_ff",
            "Multi-factor (Fama-French/Carhart) exposure regression.",
            _scalar_params(
                ["asset_returns", "factors"],
                {
                    "asset_returns": {"type": "array", "items": {"type": "number"}},
                    "factors": {"type": "object", "description": "Map of factor name -> returns array"},
                    "risk_free_rate": {"type": "number"},
                    "periods_per_year": {"type": "integer"},
                },
            ),
            h_quant_ff,
        ),
        Tool(
            "quant_backtest",
            "Backtest a supplied sequence of target weights with explicit costs.",
            _spec_param(
                "Backtest spec: {returns: {asset: [..]}, weights: [{asset: w}, ..], "
                "optional cost_bps, slippage_bps, periods_per_year}."
            ),
            h_quant_backtest,
        ),
        Tool(
            "quant_momentum",
            "Walk-forward momentum backtest (top_k by trailing return), OOS vs "
            "in-sample (look-ahead) side by side.",
            _scalar_params(
                ["returns", "lookback", "top_k", "min_train"],
                {
                    "returns": {"type": "object", "description": "Map of asset -> returns array"},
                    "lookback": {"type": "integer"},
                    "top_k": {"type": "integer"},
                    "min_train": {"type": "integer"},
                    "window": {"type": "integer", "description": "Rolling window or null for expanding"},
                    "cost_bps": {"type": "number"},
                    "slippage_bps": {"type": "number"},
                    "periods_per_year": {"type": "integer"},
                },
            ),
            h_quant_momentum,
        ),
        # fixed income
        Tool(
            "fixedincome_price",
            "Clean price of a bond given coupon, maturity, and yield "
            "(semiannual by default).",
            _scalar_params(
                ["maturity_years", "ytm"],
                {
                    "coupon_rate": {"type": "number", "description": "Annualized, e.g. 0.05"},
                    "maturity_years": {"type": "number", "description": "Years to maturity"},
                    "ytm": {"type": "number", "description": "Annualized yield-to-maturity"},
                    "face": {"type": "number", "description": "Par/face value (default 100)"},
                    "payments_per_year": {"type": "integer", "description": "Default 2"},
                },
            ),
            h_fixedincome_price,
        ),
        Tool(
            "fixedincome_ytm",
            "Solve yield-to-maturity from a bond's clean price.",
            _scalar_params(
                ["price", "maturity_years"],
                {
                    "price": {"type": "number", "description": "Clean price"},
                    "coupon_rate": {"type": "number", "description": "Annualized, e.g. 0.05"},
                    "maturity_years": {"type": "number"},
                    "face": {"type": "number"},
                    "payments_per_year": {"type": "integer"},
                },
            ),
            h_fixedincome_ytm,
        ),
        Tool(
            "fixedincome_risk",
            "Macaulay/modified duration, convexity, and DV01 for a bond.",
            _scalar_params(
                ["maturity_years", "ytm"],
                {
                    "coupon_rate": {"type": "number"},
                    "maturity_years": {"type": "number"},
                    "ytm": {"type": "number"},
                    "face": {"type": "number"},
                    "payments_per_year": {"type": "integer"},
                },
            ),
            h_fixedincome_risk,
        ),
        Tool(
            "fixedincome_curve",
            "Yield-curve ops: bootstrap par->spot {par_tenors, par_yields}, "
            "interpolate a spot {tenors, spots, t}, implied forward "
            "{rate_t1, rate_t2, t1, t2}, or discount cash flows "
            "{cashflows, times, [rate | tenors+spots]}.",
            _spec_param(
                "Curve spec: one of {par_tenors, par_yields}, {rate_t1, rate_t2, t1, t2}, "
                "{tenors, spots, t}, or {cashflows, times, rate|tenors+spots}; "
                "optional compounding (periods/year or 'continuous')."
            ),
            h_fixedincome_curve,
        ),
        # derivatives
        Tool(
            "derivatives_price",
            "Black-Scholes European option value (call or put) given spot, "
            "strike, time, rate, vol, and dividend yield.",
            _scalar_params(
                ["call_put", "S", "K", "T", "sigma"],
                {
                    "call_put": {"type": "string", "description": "'call' or 'put'"},
                    "S": {"type": "number", "description": "Spot price"},
                    "K": {"type": "number", "description": "Strike price"},
                    "T": {"type": "number", "description": "Time to expiry in years"},
                    "sigma": {"type": "number", "description": "Annualized volatility, e.g. 0.20"},
                    "r": {"type": "number", "description": "Risk-free rate (continuous, default 0)"},
                    "q": {"type": "number", "description": "Dividend yield (default 0)"},
                },
            ),
            h_derivatives_price,
        ),
        Tool(
            "derivatives_greeks",
            "Closed-form Black-Scholes Greeks (delta, gamma, vega, theta, rho).",
            _scalar_params(
                ["call_put", "S", "K", "T", "sigma"],
                {
                    "call_put": {"type": "string", "description": "'call' or 'put'"},
                    "S": {"type": "number"},
                    "K": {"type": "number"},
                    "T": {"type": "number", "description": "Years to expiry"},
                    "sigma": {"type": "number", "description": "Annualized volatility"},
                    "r": {"type": "number", "description": "Risk-free rate (default 0)"},
                    "q": {"type": "number", "description": "Dividend yield (default 0)"},
                },
            ),
            h_derivatives_greeks,
        ),
        Tool(
            "derivatives_implied_vol",
            "Solve the volatility implied by a market option price (bisection; "
            "raises if the price violates no-arbitrage bounds).",
            _scalar_params(
                ["price", "call_put", "S", "K", "T"],
                {
                    "price": {"type": "number", "description": "Market option price"},
                    "call_put": {"type": "string", "description": "'call' or 'put'"},
                    "S": {"type": "number"},
                    "K": {"type": "number"},
                    "T": {"type": "number", "description": "Years to expiry"},
                    "r": {"type": "number", "description": "Risk-free rate (default 0)"},
                    "q": {"type": "number", "description": "Dividend yield (default 0)"},
                },
            ),
            h_derivatives_implied_vol,
        ),
        Tool(
            "derivatives_binomial",
            "Cox-Ross-Rubinstein binomial price (European, or American with "
            "early exercise) — the fallback for payoffs Black-Scholes cannot "
            "price closed-form.",
            _scalar_params(
                ["call_put", "S", "K", "T", "sigma"],
                {
                    "call_put": {"type": "string", "description": "'call' or 'put'"},
                    "S": {"type": "number"},
                    "K": {"type": "number"},
                    "T": {"type": "number", "description": "Years to expiry"},
                    "sigma": {"type": "number", "description": "Annualized volatility"},
                    "r": {"type": "number", "description": "Risk-free rate (default 0)"},
                    "q": {"type": "number", "description": "Dividend yield (default 0)"},
                    "steps": {"type": "integer", "description": "Tree steps (default 200)"},
                    "american": {"type": "boolean", "description": "Allow early exercise (default false)"},
                },
            ),
            h_derivatives_binomial,
        ),
        # risk management
        Tool(
            "riskmanagement_limits",
            "Check named risk limits (max/min thresholds) against current "
            "metrics and report breaches, utilization, and headroom.",
            _spec_param(
                "Limits spec: {limits: [{name, metric, threshold, direction: "
                "'max'|'min'}], metrics: {metric: current_value}}."
            ),
            h_riskmanagement_limits,
        ),
        Tool(
            "riskmanagement_stress",
            "Scenario stress test: apply factor return shocks to a "
            "portfolio's exposures and report the P&L per scenario.",
            _spec_param(
                "Stress spec: {exposures: {factor: net_exposure_currency}, "
                "scenarios: [{name, shocks: {factor: return_shock}}], "
                "optional nav (enables pnl_pct)}."
            ),
            h_riskmanagement_stress,
        ),
        Tool(
            "riskmanagement_reverse_stress",
            "Reverse stress test: solve the single-factor shock that produces "
            "exactly a target loss.",
            _spec_param(
                "Reverse-stress spec: {exposures: {factor: net_exposure}, "
                "factor, target_loss (positive loss magnitude)}."
            ),
            h_riskmanagement_reverse_stress,
        ),
        Tool(
            "riskmanagement_var_backtest",
            "Backtest VaR forecasts against realized returns (Kupiec "
            "proportion-of-failures + Christoffersen independence/conditional "
            "coverage, each with a p-value).",
            _scalar_params(
                ["var_forecasts", "realized_returns"],
                {
                    "var_forecasts": {"type": "array", "items": {"type": "number"}, "description": "VaR loss thresholds per period (positive)"},
                    "realized_returns": {"type": "array", "items": {"type": "number"}, "description": "Signed period returns, aligned with var_forecasts"},
                    "confidence": {"type": "number", "description": "VaR confidence (default 0.95)"},
                    "significance": {"type": "number", "description": "Rejection threshold (default 0.05)"},
                },
            ),
            h_riskmanagement_var_backtest,
        ),
        # m-and-a
        Tool(
            "manda_accretion",
            "Accretion/dilution of a merger: pro-forma EPS and the $/% change "
            "vs the acquirer's standalone EPS, given consideration mix, "
            "synergies, and financing costs.",
            _scalar_params(
                ["acquirer_shares", "purchase_price", "cash_portion",
                 "stock_portion", "tax_rate"],
                {
                    "acquirer_ni": {"type": "number", "description": "Acquirer standalone net income (default 0)"},
                    "acquirer_shares": {"type": "number", "description": "Acquirer shares outstanding"},
                    "target_ni": {"type": "number", "description": "Target standalone net income (default 0)"},
                    "purchase_price": {"type": "number", "description": "Total equity consideration"},
                    "cash_portion": {"type": "number", "description": "Consideration paid in cash"},
                    "stock_portion": {"type": "number", "description": "Consideration paid in stock"},
                    "acquirer_share_price": {"type": "number", "description": "Acquirer share price (needed for stock portion)"},
                    "tax_rate": {"type": "number", "description": "Marginal tax rate, e.g. 0.25"},
                    "cost_synergies": {"type": "number", "description": "Pre-tax cost synergies (default 0)"},
                    "revenue_synergies": {"type": "number", "description": "Pre-tax revenue synergies (default 0)"},
                    "new_debt_rate": {"type": "number", "description": "Interest rate on debt funding cash (default 0)"},
                    "cash_used": {"type": "number", "description": "Cash on hand used to fund cash portion (default 0)"},
                    "cash_yield": {"type": "number", "description": "Forgone yield on cash used (default 0)"},
                },
            ),
            h_manda_accretion,
        ),
        Tool(
            "manda_synergies",
            "Present-value the run-rate synergies of a merger (ramp + "
            "perpetuity) and net them against integration costs and the "
            "premium paid.",
            _scalar_params(
                ["tax_rate", "discount_rate", "ramp_years", "premium_paid"],
                {
                    "cost_synergies": {"type": "number", "description": "Annual pre-tax cost synergies (default 0)"},
                    "revenue_synergies": {"type": "number", "description": "Annual pre-tax incremental revenue (default 0)"},
                    "revenue_margin": {"type": "number", "description": "Operating margin on revenue synergies, e.g. 0.25"},
                    "tax_rate": {"type": "number", "description": "Tax rate, e.g. 0.25"},
                    "discount_rate": {"type": "number", "description": "Discount rate, e.g. 0.10"},
                    "ramp_years": {"type": "integer", "description": "Years to full run-rate"},
                    "integration_costs": {"type": "number", "description": "One-time integration costs (default 0)"},
                    "premium_paid": {"type": "number", "description": "Premium above standalone value"},
                    "growth": {"type": "number", "description": "Perpetuity growth (default 0)"},
                },
            ),
            h_manda_synergies,
        ),
        Tool(
            "manda_breakeven",
            "Solve the pre-tax run-rate cost synergies required to exactly "
            "cover a merger's premium and integration costs.",
            _scalar_params(
                ["premium_paid", "tax_rate", "discount_rate", "ramp_years"],
                {
                    "premium_paid": {"type": "number", "description": "Premium above standalone value"},
                    "integration_costs": {"type": "number", "description": "One-time integration costs (default 0)"},
                    "tax_rate": {"type": "number", "description": "Tax rate, e.g. 0.25"},
                    "discount_rate": {"type": "number", "description": "Discount rate, e.g. 0.10"},
                    "ramp_years": {"type": "integer", "description": "Years to full run-rate"},
                    "growth": {"type": "number", "description": "Perpetuity growth (default 0)"},
                },
            ),
            h_manda_breakeven,
        ),
        Tool(
            "manda_lbo",
            "Leveraged buyout model: sources & uses, a year-by-year debt "
            "schedule (FCF pays down debt), and the sponsor's exit MOIC/IRR.",
            _scalar_params(
                ["enterprise_value", "entry_debt", "ebitda_0", "ebitda_growth",
                 "years", "fcf_margin", "exit_multiple", "interest_rate"],
                {
                    "enterprise_value": {"type": "number", "description": "EV paid for the target"},
                    "existing_net_debt": {"type": "number", "description": "Target net debt at entry (default 0; negative = net cash)"},
                    "fees": {"type": "number", "description": "Transaction fees (default 0)"},
                    "entry_debt": {"type": "number", "description": "Total debt at entry"},
                    "ebitda_0": {"type": "number", "description": "Entry EBITDA"},
                    "ebitda_growth": {"type": "number", "description": "Annual EBITDA growth, e.g. 0.05"},
                    "years": {"type": "integer", "description": "Hold period in years"},
                    "fcf_margin": {"type": "number", "description": "UFCF as a fraction of EBITDA, e.g. 0.60"},
                    "exit_multiple": {"type": "number", "description": "Exit EV/EBITDA multiple, e.g. 8.0"},
                    "interest_rate": {"type": "number", "description": "Interest rate on debt, e.g. 0.06"},
                    "tax_rate": {"type": "number", "description": "Tax rate for interest shield (default 0)"},
                },
            ),
            h_manda_lbo,
        ),
        # deal memo (integration: valuation -> m-and-a -> risk)
        Tool(
            "dealmemo_run",
            "Score a whole deal in one pass: accretion/dilution, synergy value "
            "+ break-even, an optional LBO, and risk limits + scenario stress, "
            "returning a recommendation (favorable/adverse/inconclusive) "
            "derived from the numbers, with named loss cases and a "
            "falsification condition.",
            _spec_param(
                "Deal spec object. Optional 'deal_id' and 'names' "
                "{acquirer, target}. 'merger' block {acquirer_shares, "
                "purchase_price, cash_portion, stock_portion, tax_rate, "
                "discount_rate, ramp_years, premium_paid; optional acquirer_ni, "
                "target_ni, acquirer_share_price, cost_synergies, "
                "revenue_synergies, revenue_margin, new_debt_rate, cash_used, "
                "cash_yield, integration_costs, growth}. Optional 'lbo' block "
                "{enterprise_value, entry_debt, ebitda_0, ebitda_growth, years, "
                "fcf_margin, exit_multiple, interest_rate; optional "
                "existing_net_debt, fees, tax_rate, hurdle_irr}. Optional "
                "'risk' block {metrics + limits, and/or exposures + scenarios; "
                "optional nav, loss_budget}. At least one block required."
            ),
            h_dealmemo_run,
        ),
        # execution & compliance
        Tool(
            "execution_order",
            "Validate + assess + cost an order (marketable, stop-side, slippage "
            "& market impact).",
            _spec_param(
                "Order spec: {instrument, side, quantity, order_type, optional "
                "limit_price/stop_price/time_in_force, market_price, adv, "
                "spread_bps, fee_bps, sigma_daily_bps, coefficient}."
            ),
            h_execution_order,
        ),
        Tool(
            "execution_impact",
            "Estimate slippage + market impact for a notional against ADV.",
            _scalar_params(
                ["notional", "adv"],
                {
                    "notional": {"type": "number"},
                    "adv": {"type": "number", "description": "Average daily volume (currency)"},
                    "spread_bps": {"type": "number"},
                    "fee_bps": {"type": "number"},
                    "sigma_daily_bps": {"type": "number"},
                    "coefficient": {"type": "number"},
                },
            ),
            h_execution_impact,
        ),
        Tool(
            "execution_ledger",
            "Record one trading decision into the append-only compliance ledger.",
            _spec_param(
                "Decision spec: {instrument, side, quantity, order_type, rationale, "
                "confidence, risk (loss case), falsify, optional reference_price/"
                "limit_price/stop_price, meta}."
            ),
            h_execution_ledger,
        ),
        # desk (multi-agent)
        Tool(
            "desk_run",
            "Run the multi-seat desk: route a brief to the right seats, each "
            "returns a finding (thesis, stance, confidence, loss case), and fold "
            "them into one verdict with consensus and dissent surfaced.",
            _scalar_params(
                ["objective"],
                {
                    "objective": {"type": "string", "description": "The question or task"},
                    "context": {"type": "string"},
                    "horizon": {"type": "string"},
                    "risk_capacity": {"type": "string"},
                    "constraints": {"type": "array", "items": {"type": "string"}},
                    "seats": {"type": "array", "items": {"type": "string"}, "description": "Optional seat names, e.g. pm, trader, quant, banker, cfo"},
                },
            ),
            h_desk,
        ),
        # provenance store
        Tool(
            "memory_record",
            "Record a durable fact or decision into the provenance store "
            "(append-only; supersede an old fact by id).",
            _scalar_params(
                ["content"],
                {
                    "content": {"type": "string", "description": "The fact text"},
                    "kind": {"type": "string", "description": "identity|directive|user|memory|decision (default memory)"},
                    "source": {"type": "string", "description": "default 'foreground'"},
                    "supersedes": {"type": "array", "items": {"type": "string"}, "description": "Fact ids this fact replaces"},
                    "note": {"type": "string"},
                },
            ),
            h_memory_record,
        ),
        Tool(
            "memory_export",
            "Read the active durable facts, grouped by kind.",
            _scalar_params([], {}),
            h_memory_export,
        ),
        Tool(
            "memory_retract",
            "Retract an active fact (marked removed, still recoverable).",
            _scalar_params(
                ["fact_id"],
                {"fact_id": {"type": "string", "description": "The fact id to retract"}},
            ),
            h_memory_retract,
        ),
    ]
    return ToolRegistry(tools)


__all__ = [
    "Tool",
    "ToolRegistry",
    "build_registry",
]
