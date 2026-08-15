"""The desk coordinator — routing, dispatch, validation, aggregation.

This is the heart of Phase 5: one harness, five specialists, a single
verdict. ``Desk.run`` takes a ``Brief`` and an executor and returns a
``Verdict``.

The executor is the seam that keeps the desk Hermes-independent. It is any
callable ``(Seat, Brief) -> Finding``. In tests and the offline CLI it is a
``scripted_executor`` that reads pre-authored findings; in a live runtime it
is a model call or a delegated subagent. The desk itself knows nothing about
how a seat's judgment is produced — it only routes, dispatches, validates,
and aggregates. That is the whole point: the multi-agent coordination logic
is portable, and the "spawn a specialist" choice lives behind one callable.
"""

from __future__ import annotations

from typing import Callable

from .brief import Brief, Finding, Verdict, aggregate
from .seats import DESK_SEATS, Seat, route

Executor = Callable[[Seat, Brief], Finding]


class Desk:
    """One harness, five seats, a single verdict.

    ``seats`` is an optional override map (``name -> Seat``); the default is
    the full five-seat roster. Routing always consults the desk's own roster,
    so a custom desk routes against its own seats.
    """

    def __init__(self, seats: dict | None = None):
        self.seats = dict(seats) if seats is not None else dict(DESK_SEATS)

    def route(self, brief: Brief) -> tuple[Seat, ...]:
        return route(brief.objective, brief.seats, self.seats)

    def run(self, brief: Brief, executor: Executor) -> Verdict:
        seated = self.route(brief)
        findings: list[Finding] = []
        for seat in seated:
            finding = executor(seat, brief)
            if finding is None:
                raise ValueError(
                    f"executor returned nothing for seat {seat.name!r}"
                )
            if not isinstance(finding, Finding):
                raise TypeError(
                    f"executor must return a Finding, "
                    f"got {type(finding).__name__}"
                )
            if finding.seat != seat.name:
                raise ValueError(
                    f"finding for seat {finding.seat!r} returned where "
                    f"{seat.name!r} was seated"
                )
            findings.append(finding)
        return aggregate(brief, findings)


def scripted_executor(findings_spec: dict) -> Executor:
    """A deterministic executor that reads findings from a dict keyed by seat.

    This is how the offline CLI and the tests exercise the real coordination
    path (route → dispatch → validate → aggregate) without a model. A seated
    seat with no entry in ``findings_spec`` raises — the desk refuses to
    aggregate a verdict from a silent specialist.
    """

    def executor(seat: Seat, brief: Brief) -> Finding:
        key = seat.name
        if key not in findings_spec:
            raise ValueError(f"no scripted finding for seat {key!r}")
        spec = dict(findings_spec[key])
        spec["seat"] = key
        return Finding(**spec)

    return executor
