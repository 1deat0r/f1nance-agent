"""High-level data API: caching + as-of + graceful fallback.

These are the entry points every other F1NANCE skill uses. Guarantees:

- cached hits return instantly and carry their original as-of timestamp;
- misses fetch live, then cache;
- daily equity price pulls degrade yfinance -> stooq, marking ``degraded``;
- a total failure raises :class:`SourceUnavailable` (never a fabricated number).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from . import sources
from .cache import DataCache, utc_now

# Conservative TTLs (seconds) so cached data never silently goes stale.
TTL_INTRADAY = 15 * 60
TTL_DAILY_PRICE = 6 * 60 * 60
TTL_MACRO = 24 * 60 * 60
TTL_FUNDAMENTALS = 7 * 24 * 60 * 60
TTL_FILINGS = 24 * 60 * 60

_default_cache: Optional[DataCache] = None


def get_cache() -> DataCache:
    global _default_cache
    if _default_cache is None:
        _default_cache = DataCache()
    return _default_cache


@dataclass
class Dataset:
    """A fetched (or cached) dataset with its provenance and as-of timestamp."""

    source: str      # "yfinance" | "stooq" | "fred" | "edgar"
    as_of: str       # the data's own timestamp (UTC-normalized where applicable)
    fetched_at: str  # when this snapshot was retrieved (UTC)
    degraded: bool   # True if it came from a fallback source
    cached: bool     # True if served from the on-disk cache
    data: Any        # the payload: {"bars": [...]}, {"observations": [...]}, ...


def _from_entry(entry: dict, cached: bool) -> Dataset:
    return Dataset(
        source=entry["source"],
        as_of=entry["as_of"],
        fetched_at=entry["fetched_at"],
        degraded=bool(entry.get("degraded", False)),
        cached=cached,
        data=entry["data"],
    )


def get_price_history(
    symbol: str,
    period: str = "5y",
    interval: str = "1d",
    auto_adjust: bool = True,
    refresh: bool = False,
    cache: Optional[DataCache] = None,
) -> Dataset:
    """Daily (or intraday, via yfinance) OHLCV history for an equity.

    Daily pulls try yfinance first, then fall back to stooq (``degraded=True``).
    Intraday pulls require yfinance; if it is unavailable we raise rather than
    silently substitute daily bars.
    """
    cache = cache if cache is not None else get_cache()
    sym = symbol.strip().upper()
    ttl = TTL_INTRADAY if interval != "1d" else TTL_DAILY_PRICE
    key = f"price/{sym}/{period}/{interval}/{'adj' if auto_adjust else 'raw'}"

    if not refresh:
        entry = cache.get(key)
        if entry is not None and cache.is_fresh(key, ttl):
            return _from_entry(entry, cached=True)

    if interval != "1d":
        payload = sources.fetch_yfinance(sym, period=period, interval=interval, auto_adjust=auto_adjust)
        source, degraded = "yfinance", False
    else:
        errors = []
        try:
            payload = sources.fetch_yfinance(sym, period=period, interval=interval, auto_adjust=auto_adjust)
            source, degraded = "yfinance", False
        except sources.SourceUnavailable as exc:
            errors.append(f"yfinance: {exc}")
            try:
                payload = sources.fetch_stooq(sources.to_stooq_symbol(sym))
                source, degraded = "stooq", True
            except sources.SourceUnavailable as exc2:
                errors.append(f"stooq: {exc2}")
                raise sources.SourceUnavailable(
                    f"no price data for {sym} (all sources unavailable): {'; '.join(errors)}"
                ) from exc2

    entry = cache.set(key, source=source, as_of=payload["as_of"], data=payload,
                      ttl_seconds=ttl, degraded=degraded)
    return _from_entry(entry, cached=False)


def get_macro_series(series_id: str, refresh: bool = False, cache: Optional[DataCache] = None) -> Dataset:
    """A single FRED macro series."""
    cache = cache if cache is not None else get_cache()
    sid = series_id.strip().upper()
    key = f"macro/{sid}"
    if not refresh:
        entry = cache.get(key)
        if entry is not None and cache.is_fresh(key, TTL_MACRO):
            return _from_entry(entry, cached=True)
    payload = sources.fetch_fred(sid)
    entry = cache.set(key, source="fred", as_of=payload["as_of"], data=payload,
                      ttl_seconds=TTL_MACRO)
    return _from_entry(entry, cached=False)


def get_company_facts(cik: str, refresh: bool = False, cache: Optional[DataCache] = None) -> Dataset:
    """SEC XBRL company facts (structured fundamentals) for a CIK."""
    cache = cache if cache is not None else get_cache()
    cik10 = sources.normalize_cik(cik)
    key = f"facts/{cik10}"
    if not refresh:
        entry = cache.get(key)
        if entry is not None and cache.is_fresh(key, TTL_FUNDAMENTALS):
            return _from_entry(entry, cached=True)
    payload = sources.fetch_sec_company_facts(cik10)
    entry = cache.set(key, source="edgar", as_of=utc_now(), data=payload,
                      ttl_seconds=TTL_FUNDAMENTALS)
    return _from_entry(entry, cached=False)


def get_filings(cik: str, refresh: bool = False, cache: Optional[DataCache] = None) -> Dataset:
    """SEC filing history (submissions) for a CIK."""
    cache = cache if cache is not None else get_cache()
    cik10 = sources.normalize_cik(cik)
    key = f"filings/{cik10}"
    if not refresh:
        entry = cache.get(key)
        if entry is not None and cache.is_fresh(key, TTL_FILINGS):
            return _from_entry(entry, cached=True)
    payload = sources.fetch_sec_submissions(cik10)
    entry = cache.set(key, source="edgar", as_of=utc_now(), data=payload,
                      ttl_seconds=TTL_FILINGS)
    return _from_entry(entry, cached=False)
