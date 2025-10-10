"""Backloop package initialization."""

from __future__ import annotations

try:
    import nest_asyncio
except Exception:
    # nest_asyncio may be unavailable at runtime; the package still functions.
    pass
else:
    # Allow nested event loops so pytest-asyncio can coexist with other runners.
    nest_asyncio.apply()

__all__: list[str] = []
