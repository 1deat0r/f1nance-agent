import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from f1nance.data.cache import DataCache, _iso, _parse_iso


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = DataCache(Path(self.tmp.name))

    def test_set_get_roundtrip(self):
        self.cache.set("k1", source="stooq", as_of="2026-08-15",
                       data={"bars": [{"date": "2026-08-15", "close": 1.0}]},
                       ttl_seconds=60)
        entry = self.cache.get("k1")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["source"], "stooq")
        self.assertEqual(entry["as_of"], "2026-08-15")
        self.assertEqual(entry["data"]["bars"][0]["close"], 1.0)
        self.assertIn("fetched_at", entry)

    def test_missing_returns_none(self):
        self.assertIsNone(self.cache.get("nope"))

    def test_corrupt_file_returns_none(self):
        self.cache.set("k", source="x", as_of="2026-01-01", data={}, ttl_seconds=1)
        self.cache._path("k").write_text("{ not json", "utf-8")
        self.assertIsNone(self.cache.get("k"))

    def test_freshness(self):
        self.cache.set("k", source="x", as_of="2026-01-01", data={}, ttl_seconds=3600)
        self.assertTrue(self.cache.is_fresh("k", 3600))
        self.assertFalse(self.cache.is_fresh("k", 0))
        self.assertFalse(self.cache.is_fresh("missing", 3600))

    def test_clear(self):
        self.cache.set("a", source="x", as_of="2026-01-01", data={}, ttl_seconds=1)
        self.cache.set("b", source="x", as_of="2026-01-01", data={}, ttl_seconds=1)
        self.assertEqual(self.cache.clear(), 2)
        self.assertEqual(self.cache.clear(), 0)

    def test_iso_normalizes_naive_datetime_to_utc(self):
        s = _iso(datetime(2026, 1, 1, 12, 0, 0))
        self.assertTrue(s.endswith("+00:00"))
        parsed = _parse_iso(s)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.hour, 12)

    def test_remove(self):
        self.cache.set("k", source="x", as_of="2026-01-01", data={}, ttl_seconds=1)
        self.assertTrue(self.cache.remove("k"))
        self.assertFalse(self.cache.remove("k"))
        self.assertIsNone(self.cache.get("k"))


if __name__ == "__main__":
    unittest.main()
