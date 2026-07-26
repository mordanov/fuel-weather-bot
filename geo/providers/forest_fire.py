"""
ForestFireProvider — NASA FIRMS active fire data (MODIS/VIIRS, 24h).

Public endpoint, no API key required for basic CSV access.
"""

from __future__ import annotations

import csv
import io
import logging
import math

import httpx

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)

# NASA FIRMS public CSV endpoint (VIIRS S-NPP 24h, global)
_FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/VIIRS_SNPP_NRT/world/1"

_DEFAULT_RADIUS_KM = 100


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class ForestFireProvider(GeoDataProvider):
    provider_name = "forest_fire"
    cache_ttl = 3600  # data updates every ~3h

    def __init__(self, radius_km: int = _DEFAULT_RADIUS_KM) -> None:
        self._radius_km = radius_km

    async def get_data(self, location: Location) -> GeoResult:
        # Bounding box ±radius
        deg = self._radius_km / 111.0
        bbox = f"{location.lon - deg:.3f},{location.lat - deg:.3f},{location.lon + deg:.3f},{location.lat + deg:.3f}"
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/VIIRS_SNPP_NRT/{bbox}/1"

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            content = resp.text
            reader = csv.DictReader(io.StringIO(content))
            fires = []
            for row in reader:
                try:
                    flat = float(row.get("latitude", 0))
                    flon = float(row.get("longitude", 0))
                    dist = _haversine_km(location.lat, location.lon, flat, flon)
                    if dist <= self._radius_km:
                        fires.append({
                            "lat": flat,
                            "lon": flon,
                            "brightness": row.get("bright_ti4"),
                            "frp": row.get("frp"),
                            "date": row.get("acq_date"),
                            "time": row.get("acq_time"),
                            "distance_km": round(dist, 1),
                        })
                except (ValueError, KeyError):
                    continue
            fires.sort(key=lambda f: f["distance_km"])
            return self._ok({"fires": fires, "count": len(fires), "radius_km": self._radius_km})
        except Exception as exc:
            logger.warning("ForestFireProvider: %s", exc)
            return self._fail(str(exc))
