"""F1NANCE data substrate — fetch/cache layer with as-of discipline.

Hermes-independent by design: the core (stooq, FRED, SEC EDGAR, caching) runs
on the Python standard library alone. yfinance is an optional enhancement that
degrades to stooq when unavailable — never to a fabricated value.
"""

from .api import (
    Dataset,
    get_company_facts,
    get_filings,
    get_macro_series,
    get_price_history,
)
from .cache import DataCache
from .sources import SourceUnavailable

__version__ = "0.1.0"

__all__ = [
    "Dataset",
    "DataCache",
    "SourceUnavailable",
    "get_price_history",
    "get_macro_series",
    "get_company_facts",
    "get_filings",
    "__version__",
]
