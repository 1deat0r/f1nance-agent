"""F1NANCE desk — the Phase-5 multi-agent coordination layer.

Hermes-independent, stdlib-only. One harness, five seats (PM, trader, quant,
banker, CFO) over the six capability domains, and a single verdict. A task
enters as a ``Brief``, is routed to the seats that own it, each seat returns
a ``Finding`` (thesis + stance + confidence + loss case + falsification), and
the coordinator folds them into a ``Verdict`` where consensus and dissent are
surfaced and every loss case survives aggregation.

A seat's *judgment* is produced by an injectable ``executor`` — the seam that
keeps this layer portable. In tests and the offline CLI it is scripted; in a
live runtime it is a model call or a delegated subagent. The desk itself
knows nothing about how a seat thinks, only how to coordinate it.

Three modules:

- ``seats`` — the roster (five seats, each mapped to its domain, roles,
  engines, and routing keywords) and deterministic routing.
- ``brief`` — the task/output models (``Brief``, ``Finding``, ``Verdict``)
  with structural validation, and the ``aggregate`` fold.
- ``desk`` — the ``Desk`` coordinator (route → dispatch → validate →
  aggregate) plus the ``scripted_executor`` for offline runs.
"""

from .brief import STANCES, Brief, Finding, Verdict, aggregate
from .desk import Desk, Executor, scripted_executor
from .seats import DESK_SEATS, ROSTER_ORDER, Seat, get_seat, route

__version__ = "0.1.0"

__all__ = [
    "Brief",
    "Finding",
    "Verdict",
    "STANCES",
    "aggregate",
    "Desk",
    "Executor",
    "scripted_executor",
    "DESK_SEATS",
    "ROSTER_ORDER",
    "Seat",
    "get_seat",
    "route",
    "__version__",
]
