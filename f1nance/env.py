"""Environment loading for the F1NANCE runtime (stdlib-only, no dotenv).

The standalone agent and the desk's live executor read their credentials from
the process environment (``F1NANCE_API_KEY`` / ``DEEPSEEK_API_KEY``). This
module lets the body own its key: :func:`load_env` reads ``f1nance/.env``
(gitignored) into ``os.environ`` before the clients build, so live runs work
without hand-sourcing the retired Hermes profile's old ``.env``.

Rules (matching python-dotenv semantics, but stdlib-only):

- Existing environment variables are **never** overwritten — a key the caller
  already set always wins over the file.
- Blank lines, ``#`` comments, and ``export `` prefixes are ignored/handled.
- A missing file is a no-op (empty dict), so a checkout without a ``.env``
  still runs offline.
"""

from __future__ import annotations

import os
from pathlib import Path

_BODY = Path(__file__).resolve().parent  # f1nance/


def default_env_path() -> Path:
    """The canonical env file — ``f1nance/.env`` (``F1NANCE_ENV`` overrides)."""
    env = os.environ.get("F1NANCE_ENV")
    if env:
        return Path(env)
    return _BODY / ".env"


def load_env(path: str | Path | None = None) -> dict:
    """Load ``KEY=VALUE`` pairs into ``os.environ``, never overwriting.

    Returns the mapping of keys actually set (existing environment wins, so a
    second call returns an empty dict). A missing file is a no-op.
    """
    path = Path(path) if path is not None else default_env_path()
    if not path.exists():
        return {}
    loaded: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


__all__ = ["default_env_path", "load_env"]
