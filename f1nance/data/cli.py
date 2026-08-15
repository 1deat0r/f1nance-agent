"""Command-line entry point for the F1NANCE data substrate.

Run with::

    f1nance/.venv/bin/python -m f1nance.data price AAPL --period 5y
    f1nance/.venv/bin/python -m f1nance.data macro CPIAUCSL DFF
    f1nance/.venv/bin/python -m f1nance.data facts 320193
    f1nance/.venv/bin/python -m f1nance.data filings 320193
    f1nance/.venv/bin/python -m f1nance.data cache list|clear

Emits JSON to stdout; provenance and as-of are always included so downstream
consumers (or a human) can see exactly what the number was and when it was
current.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from .api import (
    Dataset,
    get_company_facts,
    get_filings,
    get_macro_series,
    get_price_history,
)
from .cache import DataCache
from .sources import SourceUnavailable


def _emit(dataset: Dataset) -> None:
    print(json.dumps(
        {
            "source": dataset.source,
            "as_of": dataset.as_of,
            "fetched_at": dataset.fetched_at,
            "degraded": dataset.degraded,
            "cached": dataset.cached,
            "data": dataset.data,
        },
        indent=2,
        default=str,
    ))


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1nance.data",
        description="F1NANCE market-data fetch/cache layer (as-of discipline).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    price = sub.add_parser("price", help="equity OHLCV history")
    price.add_argument("symbol")
    price.add_argument("--period", default="5y")
    price.add_argument("--interval", default="1d")
    price.add_argument("--no-adjust", action="store_true", help="raw (unadjusted) prices")
    price.add_argument("--refresh", action="store_true", help="bypass the cache")

    macro = sub.add_parser("macro", help="FRED macro series (one or more IDs)")
    macro.add_argument("series", nargs="+")
    macro.add_argument("--refresh", action="store_true")

    facts = sub.add_parser("facts", help="SEC XBRL company facts by CIK")
    facts.add_argument("cik")
    facts.add_argument("--refresh", action="store_true")

    filings = sub.add_parser("filings", help="SEC filing history by CIK")
    filings.add_argument("cik")
    filings.add_argument("--refresh", action="store_true")

    cache_p = sub.add_parser("cache", help="cache management")
    cache_sub = cache_p.add_subparsers(dest="cache_cmd", required=True)
    cache_sub.add_parser("list", help="list cached entries")
    cache_sub.add_parser("clear", help="delete all cached entries")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "price":
            _emit(get_price_history(
                args.symbol, period=args.period, interval=args.interval,
                auto_adjust=not args.no_adjust, refresh=args.refresh,
            ))
        elif args.cmd == "macro":
            for sid in args.series:
                _emit(get_macro_series(sid, refresh=args.refresh))
        elif args.cmd == "facts":
            _emit(get_company_facts(args.cik, refresh=args.refresh))
        elif args.cmd == "filings":
            _emit(get_filings(args.cik, refresh=args.refresh))
        elif args.cmd == "cache":
            cache = DataCache()
            if args.cache_cmd == "list":
                for entry in cache.iter_entries():
                    print(f"{entry['key']}\t{entry['source']}\tas_of={entry['as_of']}\t"
                          f"fetched={entry['fetched_at']}\tdegraded={entry.get('degraded', False)}")
            elif args.cache_cmd == "clear":
                print(f"cleared {cache.clear()} cache entries")
    except SourceUnavailable as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
