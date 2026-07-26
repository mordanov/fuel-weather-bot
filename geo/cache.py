"""Thread-safe in-memory TTL cache for GeoResult objects."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class _Entry:
    result: object
    expires_at: float


class GeoCache:
    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}

    def get(self, key: str) -> Optional[object]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.result

    def set(self, key: str, result: object, ttl: int) -> None:
        self._store[key] = _Entry(result=result, expires_at=time.monotonic() + ttl)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        now = time.monotonic()
        return sum(1 for e in self._store.values() if e.expires_at > now)
