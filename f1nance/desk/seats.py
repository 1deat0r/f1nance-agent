"""The F1NANCE desk roster — five seats over the six capability domains.

The desk is the multi-agent layer: a task (``Brief``) is routed to one or
more seats, each seat is an independent specialist, and the coordinator
aggregates their findings into a single verdict. Each seat maps a subset of
the twelve finance roles to a capability domain and to the ``f1nance``
engines it runs on.

Hermes-independent by design: this module *models* the desk and routes tasks
deterministically. It does not know how a seat's judgment is produced — that
is the executor's job (see ``desk.py``). Nothing here imports Hermes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Seat:
    name: str        # canonical short name ("pm", "trader", ...)
    label: str       # human label ("Portfolio Manager")
    domain: str      # capability domain key (see ARCHITECTURE.md)
    roles: tuple     # the finance roles this seat serves
    engines: tuple   # f1nance subpackages it runs on
    keywords: tuple  # routing terms (case-insensitive substring match)
    mandate: str     # one-line responsibility


DESK_SEATS: dict[str, Seat] = {
    "pm": Seat(
        name="pm",
        label="Portfolio Manager",
        domain="asset-management",
        roles=(
            "Hedge Fund Manager",
            "Portfolio Manager",
            "Financial Advisor",
            "Investment Advisor",
        ),
        engines=("portfolio", "quant"),
        keywords=(
            "portfolio", "allocation", "asset", "rebalance", "concentration",
            "drawdown", "sharpe", "attribution", "exposure", "hedge",
            "position", "risk capacity", "risk tolerance", "goal", "plan",
            "retire", "suitability",
        ),
        mandate=(
            "Portfolio construction, factor/risk models, attribution, and "
            "drawdown discipline."
        ),
    ),
    "trader": Seat(
        name="trader",
        label="Trader",
        domain="markets-and-trading",
        roles=("Macro Sales & Trading", "Equities Sales & Trading"),
        engines=("execution", "data"),
        keywords=(
            "trade", "order", "execute", "execution", "slippage", "spread",
            "cost", "entry", "exit", "timing", "macro", "rates", "fx",
            "credit", "vol", "inflation", "central bank",
        ),
        mandate=(
            "Rates/FX/credit/equity/vol views, trade ideas, and execution "
            "risk."
        ),
    ),
    "quant": Seat(
        name="quant",
        label="Quantitative Analyst",
        domain="quantitative",
        roles=("Quantitative Analyst",),
        engines=("quant",),
        keywords=(
            "model", "backtest", "factor", "regression", "stat", "pricing",
            "option", "derivative", "momentum", "alpha", "beta",
            "correlation", "quant",
        ),
        mandate=(
            "Models, statistics, backtesting, and pricing — validated, not "
            "overfit."
        ),
    ),
    "banker": Seat(
        name="banker",
        label="Investment Banker",
        domain="investment-banking",
        roles=(
            "M&A Director",
            "Investment Banking Director",
            "Senior Banker",
        ),
        engines=("data",),
        keywords=(
            "valuation", "deal", "m&a", "merger", "acquisition", "worth",
            "price target", "dcf", "multiple", "comparable", "ipo",
            "financing", "raise", "capital structure", "divest", "spin",
        ),
        mandate=(
            "Valuation, deal structuring, process, and strategic optionality."
        ),
    ),
    "cfo": Seat(
        name="cfo",
        label="Chief Financial Officer",
        domain="corporate-finance-and-accounting",
        roles=("Accountant", "Chief Financial Officer"),
        engines=("data",),
        keywords=(
            "cash", "budget", "forecast", "fpa", "statement", "balance sheet",
            "income statement", "cash flow", "close", "accounting", "audit",
            "treasury", "working capital", "capex",
        ),
        mandate=(
            "The three statements, close, FP&A, budgeting, treasury, and "
            "capital allocation."
        ),
    ),
}

# Roster order — the order seats are seated and findings reported in.
ROSTER_ORDER = ("pm", "trader", "quant", "banker", "cfo")


def get_seat(name: str, roster: dict | None = None) -> Seat:
    """Return the seat named ``name``, or raise on an unknown seat."""
    roster = roster if roster is not None else DESK_SEATS
    key = (name or "").strip().lower()
    if key not in roster:
        raise ValueError(
            f"unknown seat {name!r}; choose from {', '.join(roster)}"
        )
    return roster[key]


def route(objective: str, explicit: tuple = (), roster: dict | None = None) -> tuple[Seat, ...]:
    """Route an objective to the seats that should work it.

    ``explicit`` (non-empty) selects exactly those seats — validated, then
    returned in roster order. Otherwise the objective is matched against each
    seat's keywords (case-insensitive substring); every seat with a match is
    seated, in roster order. If nothing matches, this raises rather than
    guessing: routing is a decision, and an unroutable task must be made
    explicit rather than silently convened to the wrong seats.
    """
    roster = roster if roster is not None else DESK_SEATS
    if explicit:
        names: list[str] = []
        for n in explicit:
            key = (n or "").strip().lower()
            get_seat(key, roster)  # validate
            if key not in names:
                names.append(key)
        return tuple(roster[n] for n in roster if n in names)

    objective = (objective or "").lower()
    matched = [
        s for s in roster.values() if any(k in objective for k in s.keywords)
    ]
    if not matched:
        raise ValueError(
            "objective matched no seat's keywords; specify seats explicitly "
            f"(one or more of {', '.join(roster)})"
        )
    return tuple(matched)
