"""
PollenProvider — Open-Meteo Air Quality API pollen data.

Provides: alder, birch, grass, mugwort, olive, ragweed pollen levels.
"""

from __future__ import annotations

import logging

import httpx

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)

_AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

_POLLEN_FIELDS = [
    "alder_pollen",
    "birch_pollen",
    "grass_pollen",
    "mugwort_pollen",
    "olive_pollen",
    "ragweed_pollen",
]


def pollen_level_label(value: float | None) -> str:
    """Convert pollen grains/m³ to a descriptive label."""
    if value is None:
        return "n/a"
    if value < 10:
        return "Low"
    if value < 50:
        return "Moderate"
    if value < 200:
        return "High"
    return "Very High"


class PollenProvider(GeoDataProvider):
    provider_name = "pollen"
    cache_ttl = 3600  # 1 hour

    async def get_data(self, location: Location) -> GeoResult:
        params = {
            "latitude": location.lat,
            "longitude": location.lon,
            "current": ",".join(_POLLEN_FIELDS),
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_AQI_URL, params=params)
                resp.raise_for_status()
            current = resp.json().get("current", {})
            data = {field: current.get(field) for field in _POLLEN_FIELDS}
            return self._ok(data)
        except Exception as exc:
            logger.warning("PollenProvider: %s", exc)
            return self._fail(str(exc))
