import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from f1nance.env import default_env_path, load_env


class LoadEnvTest(unittest.TestCase):
    def test_loads_keys_and_skips_noise(self):
        with TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text(
                "F1NANCE_API_KEY=abc\n"
                "DEEPSEEK_API_KEY=def\n"
                "# a comment\n"
                "\n"
                "export F1NANCE_MODEL=deepseek-v4-pro\n"
            )
            with patch.dict(os.environ, {}, clear=True):
                loaded = load_env(path=p)
                self.assertEqual(os.environ["F1NANCE_API_KEY"], "abc")
                self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "def")
                self.assertEqual(os.environ["F1NANCE_MODEL"], "deepseek-v4-pro")
                self.assertEqual(
                    set(loaded),
                    {"F1NANCE_API_KEY", "DEEPSEEK_API_KEY", "F1NANCE_MODEL"},
                )

    def test_existing_environment_wins(self):
        with TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text("F1NANCE_API_KEY=from_file\n")
            with patch.dict(os.environ, {"F1NANCE_API_KEY": "from_env"}, clear=True):
                loaded = load_env(path=p)
                self.assertEqual(loaded, {})
                self.assertEqual(os.environ["F1NANCE_API_KEY"], "from_env")

    def test_quotes_are_stripped(self):
        with TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text('DEEPSEEK_API_KEY="sk-123"\n')
            with patch.dict(os.environ, {}, clear=True):
                load_env(path=p)
                self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "sk-123")

    def test_missing_file_is_noop(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_env(path=Path("/nonexistent/.env")), {})

    def test_default_path_is_package_anchored(self):
        p = default_env_path()
        self.assertEqual(p.name, ".env")
        self.assertIn("f1nance", str(p))


if __name__ == "__main__":
    unittest.main()
