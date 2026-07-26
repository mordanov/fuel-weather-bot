"""Abstract base class for all geo-data providers."""

from __future__ import annotations

import abc
from datetime import datetime, timezone

from geo.models import GeoResult, Location


class GeoDataProvider(abc.ABC):
    """Interface every provider must implement."""

    # Override in subclass
    provider_name: str = "base"
    cache_ttl: int = 300  # seconds

    @abc.abstractmethod
    async def get_data(self, location: Location) -> GeoResult:
        """Fetch data for the given location. Never raises — returns GeoResult.failure on error."""

    async def healthcheck(self) -> bool:
        """Return True if the provider is reachable. Default: attempt a fetch at a fixed point."""
        return True

    def _ok(self, data: dict, source: str = "live") -> GeoResult:
        return GeoResult(
            provider=self.provider_name,
            timestamp=datetime.now(timezone.utc),
            data=data,
            source=source,
        )

    def _fail(self, error: str) -> GeoResult:
        return GeoResult.failure(self.provider_name, error)
