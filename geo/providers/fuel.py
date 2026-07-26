"""
FuelProvider — wraps the existing synchronous CompositeFuelProvider in an async interface.

Runs blocking I/O in a thread-pool executor to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class FuelProvider(GeoDataProvider):
    provider_name = "fuel"
    cache_ttl = 1800  # 30 min — fuel prices change at most once per day

    def __init__(self, province_code: str, municipio_name: str = "") -> None:
        from fuel_providers import CompositeFuelProvider, ProviderConfig
        self._inner = CompositeFuelProvider(ProviderConfig.from_env())
        self._province_code = province_code
        self._municipio_name = municipio_name

    async def get_data(self, location: Location) -> GeoResult:
        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(
                None,
                lambda: self._inner.fetch(self._province_code, self._municipio_name),
            )
            return self._ok(data)
        except Exception as exc:
            logger.warning("FuelProvider: %s", exc)
            return self._fail(str(exc))
