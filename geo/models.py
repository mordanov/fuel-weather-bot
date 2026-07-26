"""Core domain models for the geo-information platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Location:
    lat: float
    lon: float
    city: str = ""
    province: str = ""
    country: str = "ES"

    def __str__(self) -> str:
        if self.city:
            return f"{self.city}, {self.province}" if self.province else self.city
        return f"{self.lat:.4f}, {self.lon:.4f}"


@dataclass
class GeoResult:
    provider: str
    timestamp: datetime
    data: dict[str, Any]
    source: str = "live"  # "live" | "cache" | "snapshot"
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @classmethod
    def failure(cls, provider: str, error: str) -> "GeoResult":
        return cls(provider=provider, timestamp=datetime.now(timezone.utc), data={}, error=error)
