import tempfile
import unittest
from pathlib import Path
from unittest import mock

from f1nance.data import SourceUnavailable, api
from f1nance.data.cache import DataCache


def _cache():
    tmp = tempfile.TemporaryDirectory()
    cache = DataCache(Path(tmp.name))
    return tmp, cache


class PriceHistoryTest(unittest.TestCase):
    def test_cached_hit_is_reused(self):
        tmp, cache = _cache()
        self.addCleanup(tmp.cleanup)
        cache.set("price/AAPL/5y/1d/adj", source="stooq", as_of="2026-08-15",
                  data={"bars": [{"date": "2026-08-15", "close": 1.0}]},
                  ttl_seconds=3600)
        with mock.patch.object(api.sources, "fetch_yfinance") as yf, \
             mock.patch.object(api.sources, "fetch_stooq") as stooq:
            ds = api.get_price_history("AAPL", cache=cache)
        yf.assert_not_called()
        stooq.assert_not_called()
        self.assertTrue(ds.cached)
        self.assertEqual(ds.source, "stooq")

    def test_yfinance_primary(self):
        tmp, cache = _cache()
        self.addCleanup(tmp.cleanup)
        payload = {"as_of": "2026-08-15", "symbol": "AAPL",
                   "bars": [{"date": "2026-08-15", "close": 2.0}]}
        with mock.patch.object(api.sources, "fetch_yfinance", return_value=payload) as yf, \
             mock.patch.object(api.sources, "fetch_stooq") as stooq:
            ds = api.get_price_history("AAPL", cache=cache)
        yf.assert_called_once()
        stooq.assert_not_called()
        self.assertEqual(ds.source, "yfinance")
        self.assertFalse(ds.degraded)
        self.assertFalse(ds.cached)

    def test_fallback_to_stooq_when_yfinance_down(self):
        tmp, cache = _cache()
        self.addCleanup(tmp.cleanup)
        payload = {"as_of": "2026-08-15", "symbol": "aapl.us",
                   "bars": [{"date": "2026-08-15", "close": 3.0}]}
        with mock.patch.object(api.sources, "fetch_yfinance",
                               side_effect=SourceUnavailable("down")), \
             mock.patch.object(api.sources, "fetch_stooq", return_value=payload) as stooq:
            ds = api.get_price_history("AAPL", cache=cache)
        stooq.assert_called_once_with("aapl.us")
        self.assertEqual(ds.source, "stooq")
        self.assertTrue(ds.degraded)

    def test_total_failure_raises(self):
        tmp, cache = _cache()
        self.addCleanup(tmp.cleanup)
        with mock.patch.object(api.sources, "fetch_yfinance",
                               side_effect=SourceUnavailable("down")), \
             mock.patch.object(api.sources, "fetch_stooq",
                               side_effect=SourceUnavailable("down")):
            with self.assertRaises(SourceUnavailable):
                api.get_price_history("AAPL", cache=cache)

    def test_intraday_requires_yfinance(self):
        tmp, cache = _cache()
        self.addCleanup(tmp.cleanup)
        with mock.patch.object(api.sources, "fetch_yfinance",
                               side_effect=SourceUnavailable("not installed")):
            with self.assertRaises(SourceUnavailable):
                api.get_price_history("AAPL", interval="1h", cache=cache)

    def test_refresh_bypasses_cache(self):
        tmp, cache = _cache()
        self.addCleanup(tmp.cleanup)
        cache.set("price/AAPL/5y/1d/adj", source="stooq", as_of="2026-08-15",
                  data={"bars": []}, ttl_seconds=3600)
        payload = {"as_of": "2026-08-16", "symbol": "AAPL",
                   "bars": [{"date": "2026-08-16", "close": 4.0}]}
        with mock.patch.object(api.sources, "fetch_yfinance", return_value=payload):
            ds = api.get_price_history("AAPL", refresh=True, cache=cache)
        self.assertFalse(ds.cached)
        self.assertEqual(ds.as_of, "2026-08-16")


class MacroTest(unittest.TestCase):
    def test_cached_hit(self):
        tmp, cache = _cache()
        self.addCleanup(tmp.cleanup)
        cache.set("macro/CPIAUCSL", source="fred", as_of="2026-03-01",
                  data={"observations": []}, ttl_seconds=3600)
        with mock.patch.object(api.sources, "fetch_fred") as fred:
            ds = api.get_macro_series("CPIAUCSL", cache=cache)
        fred.assert_not_called()
        self.assertTrue(ds.cached)

    def test_fetch_and_failure(self):
        tmp, cache = _cache()
        self.addCleanup(tmp.cleanup)
        with mock.patch.object(api.sources, "fetch_fred",
                               side_effect=SourceUnavailable("down")):
            with self.assertRaises(SourceUnavailable):
                api.get_macro_series("GDP", cache=cache)


class FactsTest(unittest.TestCase):
    def test_cik_normalized_in_key(self):
        tmp, cache = _cache()
        self.addCleanup(tmp.cleanup)
        payload = {"cik": "0000320193", "facts": {"dei": {}}}
        with mock.patch.object(api.sources, "fetch_sec_company_facts", return_value=payload):
            ds = api.get_company_facts("320193", cache=cache)
        self.assertIsNotNone(cache.get("facts/0000320193"))
        self.assertEqual(ds.source, "edgar")


if __name__ == "__main__":
    unittest.main()
