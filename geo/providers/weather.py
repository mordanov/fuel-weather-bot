"""
WeatherProvider — Open-Meteo air conditions (no API key required).
"""

from __future__ import annotations

import logging

import httpx

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)

_AIR_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherProvider(GeoDataProvider):
    provider_name = "weather"
    cache_ttl = 600  # 10 min

    async def get_data(self, location: Location) -> GeoResult:
        params = {
            "latitude": location.lat,
            "longitude": location.lon,
            "current": "temperature_2m,apparent_temperature,wind_speed_10m,wind_direction_10m,weather_code,relative_humidity_2m",
            "wind_speed_unit": "kmh",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_AIR_URL, params=params)
                resp.raise_for_status()
            current = resp.json().get("current", {})
            return self._ok({
                "temperature": current.get("temperature_2m"),
                "feels_like": current.get("apparent_temperature"),
                "wind_speed": current.get("wind_speed_10m"),
                "wind_direction": current.get("wind_direction_10m"),
                "weather_code": current.get("weather_code"),
                "humidity": current.get("relative_humidity_2m"),
            })
        except Exception as exc:
            logger.warning("WeatherProvider: %s", exc)
            return self._fail(str(exc))
