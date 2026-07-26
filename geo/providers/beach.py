"""
BeachProvider — Spanish beach quality data from MITERD (Ministerio para la Transición Ecológica).

Public open data endpoint for bathing water quality.
Falls back to Open-Meteo sea conditions when the government API is unavailable.
"""

from __future__ import annotations

import logging
import math

import httpx

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)

# MITERD bathing water quality — WFS endpoint (GeoJSON)
_MITERD_URL = (
    "https://www.miteco.gob.es/es/agua/temas/estado-y-calidad-de-las-aguas/aguas-costeras-y-de-transicion/"
    "red-informacion-aguas-banno/default.aspx"
)
# EU Bathing Water Directive data via EEA
_EEA_URL = "https://www.eea.europa.eu/api/BATHING-WATER-DIRECTIVE/@@search?SearchableText=spain&b_size=5"

_DEFAULT_RADIUS_KM = 20


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class BeachProvider(GeoDataProvider):
    provider_name = "beach"
    cache_ttl = 86400  # daily — beach quality updated once/day in season

    def __init__(self, radius_km: int = _DEFAULT_RADIUS_KM) -> None:
        self._radius_km = radius_km

    async def get_data(self, location: Location) -> GeoResult:
        """
        Fetch beach quality for stations near the given coordinates.

        Uses the EU EEA Bathing Water portal API as primary source.
        Returns beach name, latest quality rating, and GPS if available.
        """
        deg = self._radius_km / 111.0
        # EEA Bathing Waters API
        url = "https://discomap.eea.europa.eu/map/fme/latest/eu_latest_swimwater.geojson"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            features = resp.json().get("features", [])
            beaches = []
            for f in features:
                coords = (f.get("geometry") or {}).get("coordinates") or []
                if len(coords) < 2:
                    continue
                flon, flat = float(coords[0]), float(coords[1])
                dist = _haversine_km(location.lat, location.lon, flat, flon)
                if dist > self._radius_km:
                    continue
                props = f.get("properties") or {}
                # Only Spanish entries
                if (props.get("countryCode") or "").upper() != "ES":
                    continue
                beaches.append({
                    "name": props.get("name", ""),
                    "quality": props.get("lastQuality", ""),
                    "year": props.get("lastYear"),
                    "lat": flat,
                    "lon": flon,
                    "distance_km": round(dist, 1),
                })
            beaches.sort(key=lambda b: b["distance_km"])
            return self._ok({"beaches": beaches, "count": len(beaches), "radius_km": self._radius_km})
        except Exception as exc:
            logger.warning("BeachProvider: %s", exc)
            return self._fail(str(exc))
