---
name: market-data
description: "Pull real market data via f1nance/data layer: equity (yfinance/stooq), macro (FRED), filings (EDGAR)."
version: 0.2.0
author: F1NANCE Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, data, market-data, yfinance, fred, edgar, stooq]
    category: finance
    related_skills: [f1nance, valuation, macro-analysis]
---

# Market Data

The data substrate every other skill runs on. Rule one: **never fabricate a
number** — if a source is down, say the data is unavailable and degrade
gracefully. Rule two: **track as-of dates**; a price without its date is noise.

## Primary path: the `f1nance/data` layer

The fetch/cache layer in the repo (`f1nance/data/`) is the canonical way to
pull data. It caches to disk, records `as_of` + `source` + `degraded` on every
result, and degrades yfinance → stooq rather than inventing a value.

```bash
# from the repo root; runs on its own venv (NOT the shared Hermes venv)
f1nance/.venv/bin/python -m f1nance.data price AAPL --period 5y
f1nance/.venv/bin/python -m f1nance.data price AAPL --interval 1h --refresh   # intraday
f1nance/.venv/bin/python -m f1nance.data macro CPIAUCSL DFF DGS10
f1nance/.venv/bin/python -m f1nance.data facts 320193                         # CIK → XBRL fundamentals
f1nance/.venv/bin/python -m f1nance.data filings 320193
f1nance/.venv/bin/python -m f1nance.data cache list | clear
```

As a library (inside `execute_code`, run with the f1nance venv's python):

```python
from f1nance.data import get_price_history, get_macro_series, get_company_facts, SourceUnavailable
ds = get_price_history("AAPL")            # Dataset: source, as_of, fetched_at, degraded, cached, data
ds = get_macro_series("CPIAUCSL")
ds = get_company_facts("320193")
```

`as_of` is the data's own timestamp; `fetched_at` is when this snapshot was
pulled. `degraded=True` means it came from a fallback source (stooq). A total
failure raises `SourceUnavailable` — it never returns a made-up number.

## Sources by need (raw, when the layer isn't enough)

| Need | Source | How |
|---|---|---|
| Equity price history, fundamentals, options | yfinance (Yahoo) | `f1nance/data` → yfinance |
| Free daily OHLCV fallback (no key) | stooq | `f1nance/data` → stooq |
| Macro series: GDP, CPI, rates, money, employment | FRED (St. Louis Fed) | `f1nance/data` → FRED |
| SEC filings: 10-K/10-Q/8-K, XBRL facts, insider | SEC EDGAR | `f1nance/data` → EDGAR |
| News, research, sentiment | `web_search` / `web_extract` | keyless DDG backend |

## yfinance (equities & fundamentals)

- `auto_adjust=True` (default in the layer) back-adjusts for splits/dividends
  — correct for return math, wrong for raw-price levels; know which you need.
  Pass `--no-adjust` for raw.
- `t.info` is a cached dict of mixed reliability; prefer statement objects for
  financials.
- **Pitfall:** `history` rows are exchange-local-time; the layer normalizes
  as-of to UTC at the cache boundary. Never compare a US close to an EU close
  without normalizing.
- **Rate limits:** Yahoo throttles aggressively; the layer caches and only
  refetches on TTL expiry or `--refresh`.

## FRED (macro)

- `f1nance/data` hits
  `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>`. The CSV's date
  column is **`observation_date`** (not `DATE`); the layer handles both.
- Useful IDs: `DFF` (Fed funds), `CPIAUCSL` (CPI), `PCEPI` (PCE), `GDP`,
  `UNRATE` (unemployment), `DGS10`/`DGS2` (10y/2y Treasury), `T10Y2Y`
  (10y-2y spread), `BAMLH0A0HYM2` (HY OAS), `M2SL` (M2), `VIXCLS` (VIX).
- **Pitfall:** real vs. nominal — state which you're using; comparing a real
  series to a nominal one is a classic error.

## SEC EDGAR (filings)

- Company facts (XBRL): `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`
- Submissions (filing list): `https://data.sec.gov/submissions/CIK##########.json`
- Full-text search: `https://efts.sec.gov/LATEST/search-index?q=%22...%22`
- **User-Agent is mandatory and must include a contact email** — EDGAR returns
  HTTP 403 without one. The layer defaults to `contact@example.com`; set
  `F1NANCE_SEC_CONTACT` to a real address before heavy use. CIK is zero-padded
  to 10 digits (the layer's `normalize_cik` does this for you).

## stooq (free daily fallback)

- `https://stooq.com/q/d/l/?s=<ticker>.us&i=d` — the layer uses this when
  yfinance is missing or down (marks `degraded=True`).
- **Pitfall:** stooq lags by a day and has sparse coverage for small caps/ETFs;
  treat it as a fallback, never primary. The layer will *not* substitute stooq
  daily bars for an intraday request — it raises instead.

## Working discipline

1. **Prefer the layer.** It caches, records as-of, and degrades honestly.
2. **Record the as-of date** alongside every number you carry forward.
3. **Degrade gracefully.** If yfinance is throttled, the layer falls back to
   stooq; if FRED is down, it says so rather than substituting a stale value.
4. **Beware survivorship and adjustment.** Split-adjusted vs. raw prices,
   point-in-time vs. restated fundamentals — state which you used.
5. **Reuse the cache.** The layer's TTLs (intraday 15m, daily 6h, macro 24h,
   fundamentals 7d, filings 24h) keep repeated pulls cheap and consistent.
