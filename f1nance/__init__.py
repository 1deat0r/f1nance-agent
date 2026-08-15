"""F1NANCE native core — the seed of the standalone financial agent.

This directory is F1NANCE's body, distinct from the Hermes runtime that
currently bootstraps it. The ``data`` subpackage is the Phase-1 data substrate
(fetch/cache layer with as-of discipline); the ``portfolio`` subpackage is the
Phase-2 portfolio & risk engine (positions, risk metrics, attribution); the
``quant`` subpackage is the Phase-3 quant & backtesting engine (regression,
factor models, walk-forward backtesting); the ``execution`` subpackage is the
Phase-4 execution & compliance layer (orders, transaction costs, and the
append-only trade log); the ``desk`` subpackage is the Phase-5 multi-agent
coordination layer (five seats, one verdict, executor-injected); the ``core``
subpackage is the Phase-5 store-first evolution loop (provenance-aware
memory/decision store); and the ``agent`` subpackage is the Phase-6 standalone
runtime (own entry point, tool registry, and memory substrate — no Hermes).
"""

__version__ = "0.7.0"
