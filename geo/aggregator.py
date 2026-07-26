"""GeoDataAggregator — runs providers concurrently with per-provider timeout, cache, and logging."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from geo.cache import GeoCache
from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)


class GeoDataAggregator:
    """
    Runs a registered set of providers concurrently for a given location.

    Each provider result is cached for provider.cache_ttl seconds.
    A per-provider timeout prevents slow sources from blocking the response.
    """

    def __init__(
        self,
        providers: list[GeoDataProvider],
        default_timeout: float = 10.0,
    ) -> None:
        self._providers: dict[str, GeoDataProvider] = {p.provider_name: p for p in providers}
        self._default_timeout = default_timeout
        self._cache = GeoCache()

    def register(self, provider: GeoDataProvider) -> None:
        self._providers[provider.provider_name] = provider

    def unregister(self, name: str) -> None:
        self._providers.pop(name, None)

    async def gather(
        self,
        location: Location,
        include: Optional[list[str]] = None,
    ) -> dict[str, GeoResult]:
        """
        Fetch all (or a named subset of) providers concurrently.

        Returns a dict mapping provider_name → GeoResult.
        Never raises.
        """
        targets = (
            [self._providers[n] for n in include if n in self._providers]
            if include
            else list(self._providers.values())
        )
        tasks = [self._fetch_one(p, location) for p in targets]
        results_list = await asyncio.gather(*tasks, return_exceptions=False)
        return {r.provider: r for r in results_list}

    async def get(self, provider_name: str, location: Location) -> GeoResult:
        """Fetch a single provider by name."""
        provider = self._providers.get(provider_name)
        if provider is None:
            return GeoResult.failure(provider_name, f"provider '{provider_name}' not registered")
        return await self._fetch_one(provider, location)

    async def _fetch_one(self, provider: GeoDataProvider, location: Location) -> GeoResult:
        cache_key = f"{provider.provider_name}:{location.lat:.4f}:{location.lon:.4f}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            result = cached
            result.source = "cache"
            logger.debug("%s: cache hit", provider.provider_name)
            return result

        t0 = time.monotonic()
        try:
            result = await asyncio.wait_for(
                provider.get_data(location),
                timeout=self._default_timeout,
            )
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - t0
            logger.warning("%s: timed out after %.1fs", provider.provider_name, elapsed)
            result = GeoResult.failure(provider.provider_name, f"timed out after {elapsed:.1f}s")
        except Exception as exc:
            logger.error("%s: unexpected error: %s", provider.provider_name, exc, exc_info=True)
            result = GeoResult.failure(provider.provider_name, str(exc))

        elapsed = time.monotonic() - t0
        if result.ok:
            self._cache.set(cache_key, result, provider.cache_ttl)
            logger.info("%s: ok in %.2fs", provider.provider_name, elapsed)
        else:
            logger.warning("%s: failed in %.2fs: %s", provider.provider_name, elapsed, result.error)

        return result
