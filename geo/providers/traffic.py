"""
TrafficProvider — DGT (Dirección General de Tráfico) open data.

Uses the public REST API from infocar.dgt.es for incidents near a location.
No API key required.
"""

from __future__ import annotations

import logging
import math

import httpx

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)

_DGT_URL = "https://infocar.dgt.es/etraffic/BuscaElementos"
_DEFAULT_RADIUS_KM = 50


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class TrafficProvider(GeoDataProvider):
    provider_name = "traffic"
    cache_ttl = 300  # 5 min — traffic changes rapidly

    def __init__(self, radius_km: int = _DEFAULT_RADIUS_KM) -> None:
        self._radius_km = radius_km

    async def get_data(self, location: Location) -> GeoResult:
        deg = self._radius_km / 111.0
        params = {
            "latitud": location.lat,
            "longitud": location.lon,
            "accion": "getElementos",
            "latitudmin": location.lat - deg,
            "longitudmin": location.lon - deg,
            "latitudmax": location.lat + deg,
            "longitudmax": location.lon + deg,
            "parametros": "INCIDENCIA",
            "zoom": 10,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; GeoInfoBot/1.0)",
            "Accept": "application/json",
            "Referer": "https://infocar.dgt.es/etraffic/",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_DGT_URL, params=params, headers=headers)
                resp.raise_for_status()
            raw = resp.json()
            features = raw if isinstance(raw, list) else raw.get("features", [])
            incidents = []
            for item in features:
                props = item.get("properties") or item
                coords = (item.get("geometry") or {}).get("coordinates") or []
                flon = coords[0] if len(coords) > 1 else None
                flat = coords[1] if len(coords) > 1 else None
                dist = (
                    _haversine_km(location.lat, location.lon, flat, flon)
                    if flat and flon else None
                )
                incidents.append({
                    "type": props.get("tipo") or props.get("incidencia_tipo", ""),
                    "description": props.get("descripcion") or props.get("causa", ""),
                    "road": props.get("carretera", ""),
                    "lat": flat,
                    "lon": flon,
                    "distance_km": round(dist, 1) if dist else None,
                })
            incidents.sort(key=lambda x: (x["distance_km"] or 9999))
            return self._ok({"incidents": incidents, "count": len(incidents)})
        except Exception as exc:
            logger.warning("TrafficProvider: %s", exc)
            return self._fail(str(exc))
