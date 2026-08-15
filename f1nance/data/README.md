# F1NANCE Data Substrate

The Phase-1 fetch/cache layer every other F1NANCE skill runs on. It exists so
that a number is never fabricated and never silently stale: every dataset it
returns carries its **source**, its **as-of** timestamp, and whether it came
from the cache or a fallback source.

Hermes-independent by design: the core (stooq, FRED, SEC EDGAR, the cache)
uses only the Python standard library. yfinance is an optional enhancement
that degrades to stooq — never to an invented value.

## Install

```bash
# one-time, into the dedicated venv (NOT the shared Hermes runtime venv)
uv venv --python 3.11 f1nance/.venv
uv pip install --python f1nance/.venv/bin/python yfinance
```

## Use

```bash
# from the repo root
f1nance/.venv/bin/python -m f1nance.data price AAPL --period 5y
f1nance/.venv/bin/python -m f1nance.data macro CPIAUCSL DFF
f1nance/.venv/bin/python -m f1nance.data facts 320193
f1nance/.venv/bin/python -m f1nance.data filings 320193
f1nance/.venv/bin/python -m f1nance.data cache list
f1nance/.venv/bin/python -m f1nance.data cache clear
```

As a library:

```python
from f1nance.data import get_price_history, get_macro_series, SourceUnavailable

ds = get_price_history("AAPL")        # Dataset(source, as_of, fetched_at, degraded, cached, data)
ds = get_macro_series("CPIAUCSL")
```

## Sources and fallback

| Need                    | Primary   | Fallback                          |
|-------------------------|-----------|-----------------------------------|
| Equity OHLCV (daily)    | yfinance  | stooq (`degraded=True`)           |
| Equity OHLCV (intraday) | yfinance  | *none* — raises rather than substitute daily bars |
| Macro series            | FRED      | *none*                            |
| Fundamentals (XBRL)     | SEC EDGAR | *none*                            |
| Filing history          | SEC EDGAR | *none*                            |

A total failure raises `SourceUnavailable`. Nothing in this layer fabricates a
price, a quote, or a data point.

## As-of discipline

- Every `Dataset` carries `as_of` (the data's own timestamp) and `fetched_at`
  (when this snapshot was retrieved, UTC).
- Timestamps are normalized to UTC at the cache boundary.
- The cache is keyed by source+ticker+period+interval+adjustment, so a raw and
  an adjusted series can never collide.

## Cache

- Location: `f1nance/data/cache/` (gitignored). Override with `F1NANCE_DATA_DIR`.
- Entries are one JSON file per key, written atomically.
- TTLs (seconds): intraday 15m, daily price 6h, macro 24h, fundamentals 7d,
  filings 24h. Pass `--refresh` (or `refresh=True`) to bypass.

## Test

```bash
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests -v
```

Tests are offline (sources are mocked); they run with no network and no Hermes.
