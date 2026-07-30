"""
EVChargingProvider — OpenChargeMap API (free, no key required for basic use).

Returns EV charging stations within a radius around the location.
"""

from __future__ import annotations

import logging
import os

import httpx

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)

_OCM_URL = "https://api.openchargemap.io/v3/poi"
_DEFAULT_RADIUS_KM = 5


class EVChargingProvider(GeoDataProvider):
    provider_name = "ev_charging"
    cache_ttl = 3600  # stations don't change often

    def __init__(self, radius_km: int = _DEFAULT_RADIUS_KM) -> None:
        self._radius_km = radius_km
        self._api_key = os.getenv("OPENCHARGEMAP_API_KEY", "")

    async def get_data(self, location: Location) -> GeoResult:
        if not self._api_key:
            return self._fail(
                "OpenChargeMap API key not configured. Set OPENCHARGEMAP_API_KEY "
                "(free at https://openchargemap.org/site/developerinfo)"
            )

        params: dict = {
            "latitude": location.lat,
            "longitude": location.lon,
            "distance": self._radius_km,
            "distanceunit": "KM",
            "maxresults": 20,
            "compact": True,
            "verbose": False,
            "output": "json",
            "key": self._api_key,
        }

        headers = {"User-Agent": "GeoInfoBot/1.0"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(_OCM_URL, params=params, headers=headers)
                resp.raise_for_status()
            stations_raw = resp.json()
            stations = []
            for s in stations_raw:
                addr = s.get("AddressInfo") or {}
                connections = s.get("Connections") or []
                max_kw = max(
                    (c.get("PowerKW") or 0 for c in connections),
                    default=None,
                )
                stations.append({
                    "name": addr.get("Title", ""),
                    "address": addr.get("AddressLine1", ""),
                    "lat": addr.get("Latitude"),
                    "lon": addr.get("Longitude"),
                    "distance_km": addr.get("Distance"),
                    "num_points": s.get("NumberOfPoints"),
                    "max_kw": max_kw,
                    "operator": (s.get("OperatorInfo") or {}).get("Title", ""),
                })
            return self._ok({"stations": stations, "count": len(stations), "radius_km": self._radius_km})
        except Exception as exc:
            logger.warning("EVChargingProvider: %s", exc)
            return self._fail(str(exc))
