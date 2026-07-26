"""
AirQualityProvider — Open-Meteo Air Quality API (no API key required).

Provides: PM2.5, PM10, NO2, O3, European AQI index.
"""

from __future__ import annotations

import logging

import httpx

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)

_AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

_AQI_LABELS = {
    "en": {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"},
    "es": {1: "Buena", 2: "Aceptable", 3: "Moderada", 4: "Mala", 5: "Muy mala"},
    "ru": {1: "Хорошее", 2: "Удовлетворительное", 3: "Умеренное", 4: "Плохое", 5: "Очень плохое"},
}


def aqi_label(index: int | None, lang: str = "en") -> str:
    if index is None:
        return "n/a"
    labels = _AQI_LABELS.get(lang, _AQI_LABELS["en"])
    return labels.get(index, str(index))


class AirQualityProvider(GeoDataProvider):
    provider_name = "air_quality"
    cache_ttl = 3600  # 1 hour

    async def get_data(self, location: Location) -> GeoResult:
        params = {
            "latitude": location.lat,
            "longitude": location.lon,
            "current": "pm2_5,pm10,nitrogen_dioxide,ozone,european_aqi",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_AQI_URL, params=params)
                resp.raise_for_status()
            current = resp.json().get("current", {})
            return self._ok({
                "pm2_5": current.get("pm2_5"),
                "pm10": current.get("pm10"),
                "no2": current.get("nitrogen_dioxide"),
                "o3": current.get("ozone"),
                "european_aqi": current.get("european_aqi"),
            })
        except Exception as exc:
            logger.warning("AirQualityProvider: %s", exc)
            return self._fail(str(exc))
