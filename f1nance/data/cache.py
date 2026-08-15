"""On-disk cache for F1NANCE market data with as-of discipline.

Hermes-independent: standard library only. Every entry records its source,
its as-of timestamp (the data's own time, normalized to UTC), and when it was
fetched, so stale data can be recognized and never silently mixed across
timezones.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional


def utc_now() -> datetime:
    """Current time as a tz-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _iso(value: Any) -> str:
    """Normalize a date/datetime/str to an ISO-8601 UTC string."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc).isoformat()
    return str(value)


def _parse_iso(value: str) -> Optional[datetime]:
    """Parse an ISO-8601 string to a tz-aware UTC datetime, or None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def default_cache_root() -> Path:
    """Cache directory. Override with ``F1NANCE_DATA_DIR``.

    Defaults to ``f1nance/data/cache/`` next to this file (gitignored), so the
    cache lives with the body but never enters version control.
    """
    env = os.environ.get("F1NANCE_DATA_DIR")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent / "cache"


class DataCache:
    """A minimal JSON-file cache keyed by a canonical string key.

    Entries are stored one-per-file (SHA-1 of the key as the filename), written
    atomically (temp file + rename) so a crash mid-write never corrupts a cache
    entry.
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root is not None else default_cache_root()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    def get(self, key: str) -> Optional[dict]:
        """Return the cached entry dict, or None if absent/corrupt."""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or "data" not in data:
            return None
        return data

    def set(
        self,
        key: str,
        *,
        source: str,
        as_of: Any,
        data: Any,
        ttl_seconds: int,
        degraded: bool = False,
    ) -> dict:
        """Store an entry and return it."""
        entry = {
            "key": key,
            "source": source,
            "as_of": _iso(as_of),
            "fetched_at": _iso(utc_now()),
            "ttl_seconds": int(ttl_seconds),
            "degraded": bool(degraded),
            "data": data,
        }
        path = self._path(key)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entry, ensure_ascii=False, default=str), "utf-8")
        tmp.replace(path)
        return entry

    def is_fresh(self, key: str, ttl_seconds: int) -> bool:
        """True if the entry exists and was fetched within ``ttl_seconds``."""
        entry = self.get(key)
        if entry is None:
            return False
        fetched = _parse_iso(entry.get("fetched_at", ""))
        if fetched is None:
            return False
        return (utc_now() - fetched).total_seconds() < ttl_seconds

    def remove(self, key: str) -> bool:
        path = self._path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def iter_entries(self):
        """Yield cached entry dicts, most recently written first."""
        for path in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and "data" in data:
                yield data

    def clear(self) -> int:
        """Delete every cached entry; return the number removed."""
        removed = 0
        for path in self.root.glob("*.json"):
            path.unlink()
            removed += 1
        return removed
