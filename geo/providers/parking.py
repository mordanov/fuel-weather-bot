"""
ParkingProvider — Overpass API (OpenStreetMap) parking facilities near a location.

No API key required.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import httpx

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)

_OVERPASS_URL = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
_DEFAULT_RADIUS_M = 1000


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _osm_address(tags: dict) -> Optional[str]:
    street = tags.get("addr:street", "")
    num = tags.get("addr:housenumber", "")
    if street:
        return f"{street} {num}".strip() if num else street
    return None


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
                dist = round(_haversine_km(location.lat, location.lon, lat, lon), 2) if lat and lon else None
                lots.append({
                    "name": tags.get("name", ""),
                    "address": _osm_address(tags),
                    "access": tags.get("access", ""),
                    "capacity": tags.get("capacity"),
                    "fee": tags.get("fee", ""),
                    "lat": lat,
                    "lon": lon,
                    "distance_km": dist,
                })
            lots.sort(key=lambda x: (x["distance_km"] or 9999))
            return self._ok({"lots": lots, "count": len(lots), "radius_m": self._radius_m})
        except Exception as exc:
            logger.warning("ParkingProvider: %s", exc)
            return self._fail(str(exc))
