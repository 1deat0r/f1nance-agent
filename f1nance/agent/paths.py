"""Path resolution for the F1NANCE standalone agent.

Both the system prompt (``SOUL.md``) and the provenance store have a canonical
location in the body repo, independent of the process working directory. These
helpers resolve those paths from the package location (and honor the
``F1NANCE_STORE`` override) so the agent behaves the same no matter where it is
launched from.
"""

from __future__ import annotations

import os
from pathlib import Path

_PKG = Path(__file__).resolve().parent
_BODY = _PKG.parent  # f1nance/


def default_soul_path() -> Path:
    """The canonical SOUL.md — ``f1nance/SOUL.md`` next to this package."""
    return _BODY / "SOUL.md"


def default_store_path() -> str:
    """The canonical provenance store path.

    ``F1NANCE_STORE`` overrides; the default is ``f1nance/core/store.json``
    resolved from the package location (not the CWD), so the agent always
    reads and writes the body's own store.
    """
    env = os.environ.get("F1NANCE_STORE")
    if env:
        return env
    return str(_BODY / "core" / "store.json")
