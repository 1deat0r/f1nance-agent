import unittest
from unittest import mock

from f1nance.data import sources
from f1nance.data.sources import SourceUnavailable, normalize_cik, to_stooq_symbol


class NormalizeTest(unittest.TestCase):
    def test_normalize_cik(self):
        self.assertEqual(normalize_cik("320193"), "0000320193")
        self.assertEqual(normalize_cik("0000320193"), "0000320193")
        self.assertEqual(normalize_cik("CIK0000320193"), "0000320193")

    def test_normalize_cik_rejects_no_digits(self):
        with self.assertRaises(SourceUnavailable):
            normalize_cik("abc")

    def test_to_stooq_symbol(self):
        self.assertEqual(to_stooq_symbol("AAPL"), "aapl.us")
        self.assertEqual(to_stooq_symbol("aapl.uk"), "aapl.uk")


class StooqTest(unittest.TestCase):
    CSV = (
        "Date,Open,High,Low,Close,Volume\n"
        "2026-08-14,100.0,110.0,95.0,105.0,1000\n"
        "2026-08-15,105.0,115.0,100.0,110.5,2000\n"
    )

    def test_parse(self):
        with mock.patch.object(sources, "_http_get", return_value=self.CSV.encode()):
            out = sources.fetch_stooq("aapl.us")
        self.assertEqual(out["as_of"], "2026-08-15")
        self.assertEqual(len(out["bars"]), 2)
        self.assertEqual(out["bars"][-1]["close"], 110.5)
        self.assertEqual(out["bars"][-1]["volume"], 2000)

    def test_no_data_raises(self):
        with mock.patch.object(sources, "_http_get", return_value=b"No data"):
            with self.assertRaises(SourceUnavailable):
                sources.fetch_stooq("aapl.us")


class FredTest(unittest.TestCase):
    CSV = "observation_date,CPIAUCSL\n2026-01-01,320.5\n2026-02-01,.\n2026-03-01,321.0\n"

    def test_parse_skips_missing_cells(self):
        with mock.patch.object(sources, "_http_get", return_value=self.CSV.encode()):
            out = sources.fetch_fred("CPIAUCSL")
        self.assertEqual(out["as_of"], "2026-03-01")
        self.assertEqual(len(out["observations"]), 2)  # the "." row is skipped
        self.assertEqual(out["observations"][0]["value"], 320.5)

    def test_accepts_legacy_DATE_header(self):
        legacy = "DATE,CPIAUCSL\n2026-01-01,1.0\n"
        with mock.patch.object(sources, "_http_get", return_value=legacy.encode()):
            out = sources.fetch_fred("CPIAUCSL")
        self.assertEqual(out["as_of"], "2026-01-01")

    def test_empty_raises(self):
        with mock.patch.object(sources, "_http_get", return_value=b""):
            with self.assertRaises(SourceUnavailable):
                sources.fetch_fred("CPIAUCSL")

    def test_bad_header_raises(self):
        with mock.patch.object(sources, "_http_get", return_value=b"nonsense,header\n"):
            with self.assertRaises(SourceUnavailable):
                sources.fetch_fred("CPIAUCSL")


class EdgarTest(unittest.TestCase):
    def test_user_agent_has_contact(self):
        fake_json = b'{"cik": "0000320193", "entityName": "Apple Inc"}'
        with mock.patch.object(sources, "_http_get", return_value=fake_json) as get:
            sources.fetch_sec_submissions("320193")
            _, kwargs = get.call_args
            ua = kwargs["headers"]["User-Agent"]
            self.assertTrue(ua.startswith("F1NANCE Agent/"))
            self.assertIn("@", ua)  # SEC 403s on a UA without a contact

    def test_user_agent_env_override(self):
        with mock.patch.dict("os.environ", {"F1NANCE_SEC_CONTACT": "ops@real.example"}):
            self.assertTrue(sources._user_agent().endswith("ops@real.example"))

    def test_cik_in_url(self):
        fake_json = b'{"cik": "0000320193"}'
        with mock.patch.object(sources, "_http_get", return_value=fake_json) as get:
            sources.fetch_sec_submissions("320193")
            url = get.call_args[0][0]
            self.assertIn("CIK0000320193", url)


class YFinanceMissingTest(unittest.TestCase):
    def test_raises_when_not_installed(self):
        with mock.patch.dict("sys.modules", {"yfinance": None}):
            with self.assertRaises(SourceUnavailable):
                sources.fetch_yfinance("AAPL")


if __name__ == "__main__":
    unittest.main()
