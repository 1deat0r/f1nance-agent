"""The deal memo — one scored verdict over the whole deal.

Hermes-independent, stdlib-only (``math`` + ``dataclasses``). The deal memo is
the integration layer that chains three engines into a single checkable
contract: the M&A engine (accretion/dilution, synergy value + break-even, and
an optional LBO) and the risk-management engine (risk limits + scenario
stress). Where the individual engines each answer one question, the memo
answers *the* question — is this deal, on the numbers, favorable or adverse —
and does so **derived from the numbers**, never hand-waved.

Every engine call that fails on degenerate or missing input is recorded as
``not_computed`` rather than silently dropped or fabricated: a memo that could
not compute a section says so, by section, with the reason. The recommendation
is a pure function of the scorecard:

- any check **fails** → ``adverse`` (the failing checks and loss cases named);
- no failure but some in-scope check was **skipped** (e.g. an LBO without a
  hurdle, a stress test without a loss budget) or nothing could be computed →
  ``inconclusive``;
- otherwise → ``favorable``.

Conventions: money in one currency throughout; rates, tax, margins, and
shocks are **decimals** (``0.25`` = 25%, ``-0.30`` = -30%).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..m_and_a import (
    AccretionResult,
    LboResult,
    SynergyBreakeven,
    SynergyValue,
    accretion_dilution,
    lbo,
    synergy_breakeven,
    synergy_value,
)
from ..risk_management import (
    Limit,
    LimitsReport,
    Scenario,
    StressOutcome,
    check_limits,
    stress_test,
)

RECOMMENDATIONS = ("favorable", "adverse", "inconclusive")
VERDICTS = ("pass", "fail", "skip")


@dataclass
class Check:
    """One scorecard line: a named gate, its verdict, and the number behind it."""

    name: str
    verdict: str  # pass | fail | skip
    summary: str
    magnitude: Optional[float] = None


@dataclass
class DealMemo:
    """The full deal analysis: engine results, the scorecard, and the verdict."""

    deal_id: Optional[str] = None
    acquirer: Optional[str] = None
    target: Optional[str] = None
    accretion: Optional[AccretionResult] = None
    synergy: Optional[SynergyValue] = None
    breakeven: Optional[SynergyBreakeven] = None
    lbo: Optional[LboResult] = None
    limits: Optional[LimitsReport] = None
    stress: Optional[List[StressOutcome]] = None
    checks: List[Check] = field(default_factory=list)
    recommendation: str = "inconclusive"
    not_computed: Dict[str, str] = field(default_factory=dict)
    loss_cases: List[str] = field(default_factory=list)
    falsify: str = ""


def _section_error(exc: BaseException) -> str:
    """Render a section failure honestly: a missing field reads as missing."""
    if isinstance(exc, KeyError):
        return f"missing required field {exc.args[0]!r}"
    return str(exc)


# -- section computation -----------------------------------------------------


def _compute_merger(memo: DealMemo, merger: dict) -> None:
    """Run accretion, synergy value, and break-even on the merger block."""
    tax_rate = float(merger["tax_rate"])
    cost_synergies = float(merger.get("cost_synergies", 0.0))
    revenue_synergies = float(merger.get("revenue_synergies", 0.0))
    discount_rate = float(merger["discount_rate"])
    ramp_years = int(merger["ramp_years"])
    premium_paid = float(merger["premium_paid"])
    integration_costs = float(merger.get("integration_costs", 0.0))
    growth = float(merger.get("growth", 0.0))

    memo.accretion = accretion_dilution(
        float(merger.get("acquirer_ni", 0.0)),
        float(merger["acquirer_shares"]),
        float(merger.get("target_ni", 0.0)),
        float(merger["purchase_price"]),
        float(merger["cash_portion"]),
        float(merger["stock_portion"]),
        float(merger.get("acquirer_share_price", 0.0)),
        tax_rate,
        cost_synergies=cost_synergies,
        revenue_synergies=revenue_synergies,
        new_debt_rate=float(merger.get("new_debt_rate", 0.0)),
        cash_used=float(merger.get("cash_used", 0.0)),
        cash_yield=float(merger.get("cash_yield", 0.0)),
    )
    memo.synergy = synergy_value(
        cost_synergies,
        revenue_synergies,
        float(merger.get("revenue_margin", 0.0)),
        tax_rate,
        discount_rate,
        ramp_years,
        integration_costs,
        premium_paid,
        growth=growth,
    )
    memo.breakeven = synergy_breakeven(
        premium_paid,
        integration_costs,
        tax_rate,
        discount_rate,
        ramp_years,
        growth=growth,
    )


def _compute_lbo(memo: DealMemo, lbo_spec: dict) -> None:
    """Run the LBO model on the lbo block."""
    memo.lbo = lbo(
        float(lbo_spec["enterprise_value"]),
        float(lbo_spec.get("existing_net_debt", 0.0)),
        float(lbo_spec.get("fees", 0.0)),
        float(lbo_spec["entry_debt"]),
        float(lbo_spec["ebitda_0"]),
        float(lbo_spec["ebitda_growth"]),
        int(lbo_spec["years"]),
        float(lbo_spec["fcf_margin"]),
        float(lbo_spec["exit_multiple"]),
        float(lbo_spec["interest_rate"]),
        tax_rate=float(lbo_spec.get("tax_rate", 0.0)),
    )


def _compute_risk(memo: DealMemo, risk: dict) -> None:
    """Run the limits check and the scenario stress test on the risk block."""
    metrics = risk.get("metrics") or {}
    limits_raw = risk.get("limits")
    if metrics and limits_raw:
        limits = [
            Limit(
                name=str(lim["name"]),
                metric=str(lim["metric"]),
                threshold=float(lim["threshold"]),
                direction=str(lim.get("direction", "max")),
            )
            for lim in limits_raw
        ]
        memo.limits = check_limits(
            limits, {str(k): float(v) for k, v in metrics.items()}
        )

    exposures = risk.get("exposures") or {}
    scenarios_raw = risk.get("scenarios")
    if exposures and scenarios_raw:
        scenarios = [
            Scenario(
                name=str(sc["name"]),
                shocks={str(k): float(v) for k, v in sc["shocks"].items()},
            )
            for sc in scenarios_raw
        ]
        nav = float(risk["nav"]) if risk.get("nav") is not None else None
        memo.stress = stress_test(
            {str(k): float(v) for k, v in exposures.items()}, scenarios, nav=nav
        )

    if memo.limits is None and memo.stress is None:
        raise ValueError(
            "risk block has neither metrics+limits nor exposures+scenarios"
        )


# -- scorecard + verdict -----------------------------------------------------


def _fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def _derive(memo: DealMemo, merger: Optional[dict], lbo_spec: Optional[dict],
            risk: Optional[dict], spec: dict) -> None:
    """Score the computed sections and derive the recommendation + loss cases."""
    checks: List[Check] = []
    loss_cases: List[str] = []

    if memo.accretion is not None:
        a = memo.accretion
        if a.accretive:
            pct = f" ({a.accretion_pct:+.2%})" if a.accretion_pct is not None else ""
            checks.append(Check(
                "accretion", "pass",
                f"accretive: pro-forma EPS {a.pro_forma_eps:.4f} vs standalone "
                f"{a.standalone_eps:.4f}{pct}",
                a.accretion_abs,
            ))
        else:
            checks.append(Check(
                "accretion", "fail",
                f"dilutive: pro-forma EPS {a.pro_forma_eps:.4f} vs standalone "
                f"{a.standalone_eps:.4f} ({a.accretion_abs:+.4f}/share)",
                a.accretion_abs,
            ))
            loss_cases.append(
                f"acquirer EPS diluted by {abs(a.accretion_abs):.4f}/share")

    if memo.synergy is not None:
        s = memo.synergy
        if s.covered:
            checks.append(Check(
                "synergy coverage", "pass",
                f"net synergy value {_fmt_money(s.net_value)} covers "
                f"{_fmt_money(s.premium_paid)} premium + "
                f"{_fmt_money(s.integration_costs)} integration costs",
                s.net_value,
            ))
        else:
            checks.append(Check(
                "synergy coverage", "fail",
                f"net synergy value {_fmt_money(s.net_value)} does not cover "
                f"{_fmt_money(s.premium_paid)} premium + "
                f"{_fmt_money(s.integration_costs)} integration costs",
                s.net_value,
            ))
            loss_cases.append(
                f"premium + integration costs exceed net synergy value by "
                f"{_fmt_money(-s.net_value)}")

    if memo.lbo is not None:
        m = memo.lbo
        hurdle = lbo_spec.get("hurdle_irr") if lbo_spec else None
        if hurdle is None:
            checks.append(Check(
                "sponsor return", "skip",
                f"IRR {m.irr:.2%} / MOIC {m.moic:.2f}x reported; no hurdle_irr "
                f"supplied to gate it",
                m.irr,
            ))
        elif m.irr >= float(hurdle):
            checks.append(Check(
                "sponsor return", "pass",
                f"IRR {m.irr:.2%} meets the {float(hurdle):.1%} hurdle "
                f"(MOIC {m.moic:.2f}x)",
                m.irr,
            ))
        else:
            checks.append(Check(
                "sponsor return", "fail",
                f"IRR {m.irr:.2%} below the {float(hurdle):.1%} hurdle "
                f"(MOIC {m.moic:.2f}x)",
                m.irr,
            ))
            loss_cases.append(
                f"sponsor IRR {m.irr:.2%} falls short of the "
                f"{float(hurdle):.1%} hurdle")

    if memo.limits is not None:
        rep = memo.limits
        if rep.breach_count == 0:
            checks.append(Check(
                "risk limits", "pass",
                f"{len(rep.results)} limit(s) checked, none breached",
                rep.worst.utilization,
            ))
        else:
            checks.append(Check(
                "risk limits", "fail",
                f"{rep.breach_count} breach(es): {', '.join(rep.breached)}",
                rep.worst.utilization,
            ))
            for name in rep.breached:
                loss_cases.append(f"risk limit {name!r} breached")

    if memo.stress is not None:
        outcomes = memo.stress
        worst = min(outcomes, key=lambda o: o.pnl)
        budget = risk.get("loss_budget") if risk else None
        nav = risk.get("nav") if risk else None
        if budget is None:
            checks.append(Check(
                "stress budget", "skip",
                f"worst scenario {worst.name!r} P&L {_fmt_money(worst.pnl)}; "
                f"no loss_budget supplied to gate it",
                worst.pnl,
            ))
        elif worst.pnl >= -float(budget):
            checks.append(Check(
                "stress budget", "pass",
                f"worst scenario {worst.name!r} P&L {_fmt_money(worst.pnl)} is "
                f"within the {_fmt_money(float(budget))} budget",
                worst.pnl,
            ))
        else:
            checks.append(Check(
                "stress budget", "fail",
                f"worst scenario {worst.name!r} P&L {_fmt_money(worst.pnl)} "
                f"exceeds the {_fmt_money(float(budget))} budget",
                worst.pnl,
            ))
            loss_cases.append(
                f"worst stress scenario {worst.name!r} loses "
                f"{_fmt_money(-worst.pnl)} against a {_fmt_money(float(budget))} budget")
        if worst.pnl < 0:
            pct = f" ({worst.pnl / float(nav):.2%} of NAV)" if nav else ""
            loss_cases.insert(0,
                f"headline stress loss: {worst.name!r} scenario loses "
                f"{_fmt_money(-worst.pnl)}{pct}")

    fails = [c for c in checks if c.verdict == "fail"]
    skips = [c for c in checks if c.verdict == "skip"]
    if fails:
        memo.recommendation = "adverse"
    elif skips or not checks:
        memo.recommendation = "inconclusive"
    else:
        memo.recommendation = "favorable"

    memo.checks = checks
    memo.loss_cases = loss_cases + [str(x) for x in spec.get("loss_cases", [])]
    memo.falsify = str(spec.get("falsify", "")).strip() or _derive_falsify(
        merger, lbo_spec)


def _derive_falsify(merger: Optional[dict], lbo_spec: Optional[dict]) -> str:
    """Name the load-bearing assumption the memo would be falsified by."""
    if merger:
        try:
            pre_tax = (
                float(merger.get("cost_synergies", 0.0))
                + float(merger.get("revenue_synergies", 0.0))
                * float(merger.get("revenue_margin", 0.0))
            )
            ramp = int(merger.get("ramp_years", 2))
            return (
                f"falsified if the {_fmt_money(pre_tax)} pre-tax synergy "
                f"run-rate is not fully realized within {ramp} year(s) — "
                f"accretion and synergy coverage both assume it"
            )
        except (ValueError, TypeError):
            return ""
    if lbo_spec:
        try:
            return (
                f"falsified if the {float(lbo_spec['exit_multiple']):.1f}x "
                f"exit multiple is not achievable at exit in year "
                f"{int(lbo_spec['years'])}"
            )
        except (KeyError, ValueError, TypeError):
            return ""
    return ""


# -- entry point -------------------------------------------------------------


def build_deal_memo(spec: dict) -> DealMemo:
    """Run the deal-memo pipeline on a consolidated spec.

    ``spec`` is a dict with three optional blocks — ``merger``, ``lbo``, and
    ``risk`` — plus optional ``deal_id`` / ``names`` / ``loss_cases`` /
    ``falsify``. At least one block must be present. Each block is computed
    independently; a block that raises on degenerate or missing input is
    recorded in ``not_computed`` (with the reason) rather than fabricating a
    number. The recommendation is derived from the resulting scorecard.

    Merger block (required: ``acquirer_shares``, ``purchase_price``,
    ``cash_portion``, ``stock_portion``, ``tax_rate``, ``discount_rate``,
    ``ramp_years``, ``premium_paid``; optional with conservative defaults:
    ``acquirer_ni``, ``target_ni``, ``acquirer_share_price``, ``cost_synergies``,
    ``revenue_synergies``, ``revenue_margin``, ``new_debt_rate``, ``cash_used``,
    ``cash_yield``, ``integration_costs``, ``growth``).

    LBO block (required: ``enterprise_value``, ``entry_debt``, ``ebitda_0``,
    ``ebitda_growth``, ``years``, ``fcf_margin``, ``exit_multiple``,
    ``interest_rate``; optional: ``existing_net_debt``, ``fees``, ``tax_rate``,
    ``hurdle_irr`` — the sponsor-return check is ``skip`` without a hurdle).

    Risk block (``metrics`` + ``limits`` and/or ``exposures`` + ``scenarios``;
    optional ``nav`` and ``loss_budget`` — the stress-budget check is ``skip``
    without a ``loss_budget``).
    """
    spec = dict(spec)
    merger = spec.get("merger")
    lbo_spec = spec.get("lbo")
    risk = spec.get("risk")

    if merger is None and lbo_spec is None and risk is None:
        raise ValueError(
            "deal spec has no sections to memo — provide 'merger', 'lbo', "
            "and/or 'risk'"
        )

    names = spec.get("names") or {}
    memo = DealMemo(
        deal_id=str(spec["deal_id"]) if spec.get("deal_id") is not None else None,
        acquirer=str(names.get("acquirer")) if names.get("acquirer") else None,
        target=str(names.get("target")) if names.get("target") else None,
    )

    if merger is not None:
        try:
            _compute_merger(memo, merger)
        except (ValueError, KeyError, TypeError) as exc:
            memo.not_computed["merger"] = _section_error(exc)

    if lbo_spec is not None:
        try:
            _compute_lbo(memo, lbo_spec)
        except (ValueError, KeyError, TypeError) as exc:
            memo.not_computed["lbo"] = _section_error(exc)

    if risk is not None:
        try:
            _compute_risk(memo, risk)
        except (ValueError, KeyError, TypeError) as exc:
            memo.not_computed["risk"] = _section_error(exc)

    _derive(memo, merger, lbo_spec, risk, spec)
    return memo
