"""F1NANCE native core — the seed of the standalone financial agent.

This directory is F1NANCE's body, distinct from the Hermes runtime that
currently bootstraps it. The ``data`` subpackage is the Phase-1 data substrate
(fetch/cache layer with as-of discipline); the ``portfolio`` subpackage is the
Phase-2 portfolio & risk engine (positions, risk metrics, attribution); the
``quant`` subpackage is the Phase-3 quant & backtesting engine (regression,
factor models, walk-forward backtesting). More capability lands here as the
roadmap advances toward Hermes-independence (see ROADMAP.md → Phase 6).
"""

__version__ = "0.4.0"
