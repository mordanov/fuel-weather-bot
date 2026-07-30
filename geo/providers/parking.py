"""
ParkingProvider — Overpass API (OpenStreetMap) parking facilities near a location.

Enriches SMASSA-operated lots with live occupancy from the Málaga Open Data Portal
(updates every minute, no API key required):
  https://datosabiertos.malaga.eu/dataset/ocupacion-aparcamientos-publicos-municipales
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import math
from typing import Optional

import httpx

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)

_OVERPASS_URL = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
_SMASSA_OCCUPANCY_URL = "https://datosabiertos.malaga.eu/recursos/aparcamientos/ocupappublicosmun/ocupappublicosmun.csv"
_SMASSA_CATALOG_URL = "https://datosabiertos.malaga.eu/recursos/aparcamientos/ocupappublicosmun/catalogo.csv"
_DEFAULT_RADIUS_M = 1000

# Human-readable labels for OSM parking type values
_PARKING_TYPE_LABEL = {
    "surface": "surface",
    "street_side": "street",
    "underground": "underground",
    "multi-storey": "multi-storey",
    "rooftop": "rooftop",
    "carports": "carports",
    "garage_boxes": "garage boxes",
}

# Human-readable access labels
_ACCESS_LABEL = {
    "yes": "public",
    "permissive": "public",
    "customers": "customers only",
    "private": "private",
    "no": "closed",
}


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
    return tags.get("addr:full") or None


async def _fetch_smassa_occupancy(client: httpx.AsyncClient) -> dict[str, int]:
    """Return {smassa_id: free_spaces} from the live 1-minute CSV feed."""
    try:
        resp = await client.get(_SMASSA_OCCUPANCY_URL, timeout=8.0)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        return {row["id"].strip(): int(row["libres"]) for row in reader if row.get("id") and row.get("libres", "").strip().lstrip("-").isdigit()}
    except Exception as exc:
        logger.warning("SMASSA occupancy fetch failed: %s", exc)
        return {}


async def _fetch_smassa_catalog(client: httpx.AsyncClient) -> dict[str, dict]:
    """Return {smassa_id: {nombre, lat, lon}} from the static catalog CSV."""
    try:
        resp = await client.get(_SMASSA_CATALOG_URL, timeout=8.0)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        result = {}
        for row in reader:
            sid = row.get("id", "").strip().strip('"')
            if sid:
                result[sid] = {
                    "name": row.get("nombre", "").strip().strip('"'),
                    "address": row.get("direccion", "").strip().strip('"'),
                    "lat": float(row["latitude"]) if row.get("latitude") else None,
                    "lon": float(row["longitude"]) if row.get("longitude") else None,
                }
        return result
    except Exception as exc:
        logger.warning("SMASSA catalog fetch failed: %s", exc)
        return {}


def _match_smassa(osm_name: str, osm_lat: Optional[float], osm_lon: Optional[float],
                  catalog: dict[str, dict]) -> Optional[str]:
    """Find the best SMASSA catalog entry for an OSM lot by proximity + name."""
    if not catalog:
        return None
    best_id = None
    best_dist = 9999.0
    name_lower = osm_name.lower() if osm_name else ""
    for sid, entry in catalog.items():
        clat, clon = entry.get("lat"), entry.get("lon")
        if clat is None or clon is None:
            continue
        # Proximity match: within 150 m
        if osm_lat is not None and osm_lon is not None:
            d = _haversine_km(osm_lat, osm_lon, clat, clon) * 1000  # metres
            if d < 150 and d < best_dist:
                best_dist = d
                best_id = sid
        # Name-based fallback
        if best_id is None and name_lower:
            catalog_name = entry.get("name", "").lower()
            if catalog_name and (catalog_name in name_lower or name_lower in catalog_name):
                best_id = sid
    return best_id


class ParkingProvider(GeoDataProvider):
    provider_name = "parking"
    cache_ttl = 60  # SMASSA feed updates every minute

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
                osm_task = client.post(_OVERPASS_URL, data={"data": query})
                occupancy_task = _fetch_smassa_occupancy(client)
                catalog_task = _fetch_smassa_catalog(client)
                osm_resp, occupancy, catalog = await asyncio.gather(
                    osm_task, occupancy_task, catalog_task
                )
                osm_resp.raise_for_status()

            elements = osm_resp.json().get("elements", [])
            lots = []
            for el in elements:
                tags = el.get("tags") or {}
                lat = el.get("lat") or (el.get("center") or {}).get("lat")
                lon = el.get("lon") or (el.get("center") or {}).get("lon")
                dist = round(_haversine_km(location.lat, location.lon, lat, lon), 2) if lat and lon else None

                osm_name = tags.get("name", "")
                operator = tags.get("operator", "")
                parking_type_raw = tags.get("parking", "")

                # SMASSA live occupancy enrichment
                free_spaces = None
                if "smassa" in operator.lower() or "smassa" in osm_name.lower():
                    smassa_id = _match_smassa(osm_name, lat, lon, catalog)
                    if smassa_id and smassa_id in occupancy:
                        free_spaces = occupancy[smassa_id]

                lots.append({
                    "name": osm_name,
                    "address": _osm_address(tags),
                    "parking_type": _PARKING_TYPE_LABEL.get(parking_type_raw, parking_type_raw) or None,
                    "access": _ACCESS_LABEL.get(tags.get("access", ""), tags.get("access")) or None,
                    "fee": tags.get("fee") or None,
                    "opening_hours": tags.get("opening_hours") or None,
                    "capacity": tags.get("capacity") or None,
                    "operator": operator or None,
                    "maxheight": tags.get("maxheight") or None,
                    "supervised": tags.get("supervised") or None,
                    "free_spaces": free_spaces,
                    "lat": lat,
                    "lon": lon,
                    "distance_km": dist,
                })
            lots.sort(key=lambda x: (x["distance_km"] or 9999))
            return self._ok({"lots": lots, "count": len(lots), "radius_m": self._radius_m})
        except Exception as exc:
            logger.warning("ParkingProvider: %s", exc)
            return self._fail(str(exc))
