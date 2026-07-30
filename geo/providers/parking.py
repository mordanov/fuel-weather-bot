"""
ParkingProvider — Overpass API (OpenStreetMap) parking facilities near a location.

No API key required.
"""

from __future__ import annotations

import logging
import math

import httpx

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)

_OVERPASS_URL = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
_DEFAULT_RADIUS_M = 1000


class ParkingProvider(GeoDataProvider):
    provider_name = "parking"
    cache_ttl = 3600  # OSM data doesn't change often

    def __init__(self, radius_m: int = _DEFAULT_RADIUS_M) -> None:
        self._radius_m = radius_m

    async def get_data(self, location: Location) -> GeoResult:
        query = f"""
[out:json][timeout:10];
(
  node["amenity"="parking"](around:{self._radius_m},{location.lat},{location.lon});
  way["amenity"="parking"](around:{self._radius_m},{location.lat},{location.lon});
);
out center tags;
"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(_OVERPASS_URL, data={"data": query})
                resp.raise_for_status()
            elements = resp.json().get("elements", [])
            lots = []
            for el in elements:
                tags = el.get("tags") or {}
                lat = el.get("lat") or (el.get("center") or {}).get("lat")
                lon = el.get("lon") or (el.get("center") or {}).get("lon")
                lots.append({
                    "name": tags.get("name", ""),
                    "access": tags.get("access", ""),
                    "capacity": tags.get("capacity"),
                    "fee": tags.get("fee", ""),
                    "lat": lat,
                    "lon": lon,
                })
            return self._ok({"lots": lots, "count": len(lots), "radius_m": self._radius_m})
        except Exception as exc:
            logger.warning("ParkingProvider: %s", exc)
            return self._fail(str(exc))
