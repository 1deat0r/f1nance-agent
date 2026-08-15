"""Low-level fetchers for free market-data sources.

Hermes-independent: standard-library ``urllib`` only. yfinance is imported
lazily and is optional — its absence degrades equity price pulls to stooq,
never to a fabricated value.

Every fetcher raises :class:`SourceUnavailable` rather than returning a made-up
or partial result, so callers can fall back or report "data unavailable" with
a clear conscience.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import urllib.request
from typing import Any, Optional

# SEC requires a User-Agent with a contact (email). The default is the
# RFC-2606 reserved placeholder — set F1NANCE_SEC_CONTACT to a real address.
DEFAULT_SEC_CONTACT = "contact@example.com"

USER_AGENT = f"F1NANCE Agent/0.1.0 {DEFAULT_SEC_CONTACT}"
_TIMEOUT = 30


def _user_agent() -> str:
    contact = os.environ.get("F1NANCE_SEC_CONTACT", DEFAULT_SEC_CONTACT)
    return f"F1NANCE Agent/0.1.0 {contact}"


class SourceUnavailable(Exception):
    """A data source could not be reached or returned no usable data.

    Raised instead of ever returning a fabricated or stale value. Catch it to
    try a fallback source, or let it surface to say the data is unavailable.
    """


def normalize_cik(cik: str) -> str:
    """Normalize a CIK to the zero-padded 10-digit form SEC expects."""
    digits = "".join(ch for ch in cik if ch.isdigit())
    if not digits:
        raise SourceUnavailable(f"invalid CIK (no digits): {cik!r}")
    return digits.zfill(10)


def to_stooq_symbol(ticker: str) -> str:
    """Map a ticker to a stooq symbol (US default). ``AAPL`` -> ``aapl.us``."""
    t = ticker.strip().lower()
    return t if "." in t else f"{t}.us"


def _http_get(url: str, headers: Optional[dict] = None, timeout: int = _TIMEOUT) -> bytes:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # URLError, HTTPError, socket errors, timeouts…
        raise SourceUnavailable(f"request failed for {url}: {exc}") from exc


def _num(value: Any) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _int(value: Any) -> Optional[int]:
    f = _num(value)
    return None if f is None else int(f)


# --- stooq (free daily OHLCV, no key) ---------------------------------------

def fetch_stooq(symbol: str) -> dict:
    """Daily OHLCV bars for a stooq symbol (``aapl.us``)."""
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    raw = _http_get(url).decode("utf-8", errors="replace")
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines or not lines[0].lstrip().startswith("Date"):
        raise SourceUnavailable(f"stooq returned no usable data for {symbol}")
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    bars = []
    for row in reader:
        close = _num(row.get("Close"))
        if not row.get("Date") or close is None:
            continue
        bars.append(
            {
                "date": row["Date"],
                "open": _num(row.get("Open")),
                "high": _num(row.get("High")),
                "low": _num(row.get("Low")),
                "close": close,
                "volume": _int(row.get("Volume")),
            }
        )
    if not bars:
        raise SourceUnavailable(f"stooq returned no parseable bars for {symbol}")
    return {"as_of": bars[-1]["date"], "symbol": symbol, "bars": bars}


# --- FRED (macro series) ----------------------------------------------------

def fetch_fred(series_id: str) -> dict:
    """Observations for a FRED series (``CPIAUCSL``, ``DFF``, …)."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    raw = _http_get(url).decode("utf-8", errors="replace")
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        raise SourceUnavailable(f"FRED returned no data for {series_id}")
    reader = csv.reader(io.StringIO("\n".join(lines)))
    header = next(reader, None)
    # fredgraph.csv's date column is "observation_date" (historically "DATE").
    if not header or header[0].strip().upper() not in ("DATE", "OBSERVATION_DATE"):
        raise SourceUnavailable(f"FRED unexpected response for {series_id}: {lines[0][:60]!r}")
    observations = []
    for row in reader:
        if len(row) < 2:
            continue
        d, v = row[0].strip(), row[1].strip()
        if not d or v in ("", "."):
            continue
        value = _num(v)
        if value is None:
            continue
        observations.append({"date": d, "value": value})
    if not observations:
        raise SourceUnavailable(f"FRED returned no usable observations for {series_id}")
    return {"as_of": observations[-1]["date"], "series_id": series_id, "observations": observations}


# --- SEC EDGAR --------------------------------------------------------------

def _edgar_json(url: str) -> Any:
    raw = _http_get(url, headers={"User-Agent": _user_agent()})
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise SourceUnavailable(f"SEC returned non-JSON for {url}") from exc


def fetch_sec_company_facts(cik: str) -> dict:
    """XBRL company facts (structured fundamentals) for a CIK."""
    cik10 = normalize_cik(cik)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
    return {"cik": cik10, "facts": _edgar_json(url)}


def fetch_sec_submissions(cik: str) -> dict:
    """Filing history (submissions) for a CIK."""
    cik10 = normalize_cik(cik)
    url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    return {"cik": cik10, "submissions": _edgar_json(url)}


# --- yfinance (optional, rich equity data) ----------------------------------

def fetch_yfinance(symbol: str, period: str = "5y", interval: str = "1d", auto_adjust: bool = True) -> dict:
    """OHLCV history via yfinance (Yahoo).

    Requires yfinance to be importable (install into ``f1nance/.venv``).
    Raises :class:`SourceUnavailable` — never fabricates — if it is missing or
    returns nothing.
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise SourceUnavailable(
            "yfinance is not installed; install it into f1nance/.venv "
            "(uv pip install --python f1nance/.venv/bin/python yfinance) or use stooq"
        ) from exc

    try:
        frame = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=auto_adjust)
    except Exception as exc:
        raise SourceUnavailable(f"yfinance failed for {symbol}: {exc}") from exc

    if frame is None or getattr(frame, "empty", True):
        raise SourceUnavailable(f"yfinance returned no history for {symbol}")

    bars = []
    for idx, row in frame.iterrows():
        close = _num(row.get("Close"))
        if close is None:
            continue
        bars.append(
            {
                "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
                "open": _num(row.get("Open")),
                "high": _num(row.get("High")),
                "low": _num(row.get("Low")),
                "close": close,
                "volume": _int(row.get("Volume")),
            }
        )
    if not bars:
        raise SourceUnavailable(f"yfinance returned no parseable bars for {symbol}")
    return {"as_of": bars[-1]["date"], "symbol": symbol, "bars": bars}
