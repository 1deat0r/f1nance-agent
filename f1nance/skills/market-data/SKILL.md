---
name: market-data
description: "Pull real market data: equity prices/fundamentals (yfinance), macro series (FRED), filings (SEC EDGAR), free daily (stooq)."
version: 0.1.0
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
gracefully. Rule two: **track as-of dates**; a price without its date is
noise.

## Sources by need

| Need | Source | How |
|---|---|---|
| Equity price history, fundamentals, dividends, options | yfinance (Yahoo) | Python |
| Free daily OHLCV for many tickers (no API key) | stooq | HTTP CSV |
| Macro series: GDP, CPI, rates, money, employment | FRED (St. Louis Fed) | `fredgraph.csv` |
| SEC filings: 10-K/10-Q/8-K, XBRL facts, insider | SEC EDGAR | REST / JSON |
| News, research, sentiment, events | web_search / web_extract | keyless DDG backend |

## yfinance (equities & fundamentals)

Install into the runtime venv once (`~/.hermes/hermes-agent/venv/bin/pip
install yfinance`). Then via `execute_code` or a `terminal` python one-liner:

```python
import yfinance as yf
t = yf.Ticker("AAPL")
px = t.history(period="5y", auto_adjust=True)   # daily OHLCV DataFrame
info = t.info                                    # market cap, P/E, beta, etc.
fins = t.quarterly_income_stmt / t.balance_sheet / t.cashflow
hist = t.income_stmt  # or t.financials for annual
divs = t.dividends
```

- `auto_adjust=True` back-adjusts for splits/dividends — correct for return
  math, wrong for raw-price levels; know which you need.
- `t.info` is a cached dict of mixed reliability; prefer statement objects
  for financials.
- **Pitfall:** `history` returns data in the exchange's local timezone and
  rows are date-indexed. Never compare a US close to an EU close without
  normalizing as-of dates.
- **Rate limits:** Yahoo throttles aggressively; batch, cache to disk, and
  sleep between many-ticker pulls.

## FRED (macro)

Every series has a page `https://fred.stlouisfed.org/series/<ID>` and a
downloadable CSV at `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>`.

```bash
curl -s "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL&id=DFF&id=GDP" -o macro.csv
```

Useful IDs: `DFF` (Fed funds), `CPIAUCSL` (CPI), `PCEPI` (PCE), `GDP`,
`UNRATE` (unemployment), `DGS10`/`DGS2` (10y/2y Treasury), `T10Y2Y` (10y-2y
spread), `BAMLH0A0HYM2` (HY OAS), `M2SL` (M2), `VIXCLS` (VIX).

- Values are monthly/quarterly observations; first column is the date, second
  the value. Handle missing cells (`.`) before computing.
- **Pitfall:** real vs. nominal — CPI/GDP growth must be stated explicitly;
  comparing a real series to a nominal one is a classic error.

## SEC EDGAR (filings)

- **Full-text search:** `https://efts.sec.gov/LATEST/search-index?q=%22...%22`
  (JSON), or `https://efts.sec.gov/LATEST/search-index?q=...&forms=10-K`.
- **Company facts (XBRL, structured):**
  `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` (CIK
  zero-padded to 10 digits, no dashes).
- **Company submissions (filings list):**
  `https://data.sec.gov/submissions/CIK##########.json`.
- **Filing documents:** `https://www.sec.gov/Archives/edgar/data/<CIK>/<accession no-dashes>/<doc>.htm`.
- EDGAR requires a `User-Agent` header with a contact (`User-Agent: F1NANCE
  Agent <you@example.com>`); set it or you will be throttled/denied.

## stooq (free daily, no key)

```bash
curl -s "https://stooq.com/q/d/l/?s=aapl.us&i=d" -o aapl.csv
```

- `s=<ticker>.us` for US equities, `.uk`, `.de`, etc. for others; `i=d` daily.
- Last column is volume; first is date.
- **Pitfall:** stooq data can lag by a day and has sparse coverage for small
  caps/ETFs; treat it as a fallback, not primary.

## News & research

Use `web_search` / `web_extract` (keyless DDG backend) for news, sentiment,
and qualitative research. Prefer primary sources (company IR, regulator,
central bank) over aggregators. For a cited, verifiable document, use the
`grounded-citations` skill.

## Working discipline

1. **Cache to disk.** Don't re-hit the network for the same series in one
   session; write fetched frames to a workspace CSV/JSON.
2. **Record the as-of date** alongside every number you carry forward.
3. **Degrade gracefully.** If yfinance is throttled, try stooq; if FRED is
   down, say so rather than substituting a stale or made-up value.
4. **Beware survivorship and adjustment.** Split-adjusted vs. raw prices,
   point-in-time vs. restated fundamentals — state which you used.
