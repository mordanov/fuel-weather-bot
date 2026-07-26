"""
SeaProvider — Open-Meteo Marine API (no API key required).
"""

from __future__ import annotations

import logging

import httpx

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)

_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"


class SeaProvider(GeoDataProvider):
    provider_name = "sea"
    cache_ttl = 900  # 15 min

    async def get_data(self, location: Location) -> GeoResult:
        params = {
            "latitude": location.lat,
            "longitude": location.lon,
            "current": "sea_surface_temperature,wave_height,wave_direction,wave_period",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_MARINE_URL, params=params)
                resp.raise_for_status()
            current = resp.json().get("current", {})
            return self._ok({
                "sea_temperature": current.get("sea_surface_temperature"),
                "wave_height": current.get("wave_height"),
                "wave_direction": current.get("wave_direction"),
                "wave_period": current.get("wave_period"),
            })
        except Exception as exc:
            logger.warning("SeaProvider: %s", exc)
            return self._fail(str(exc))
