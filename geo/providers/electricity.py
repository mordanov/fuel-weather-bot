"""
ElectricityPriceProvider — Spanish electricity spot prices via REE's esios API.

Uses the public indicator endpoint (no API key for basic access).
Endpoint: https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real
"""

from __future__ import annotations

import logging
from datetime import date, timezone

import httpx

from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

logger = logging.getLogger(__name__)

_REE_URL = "https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real"


class ElectricityPriceProvider(GeoDataProvider):
    provider_name = "electricity"
    cache_ttl = 3600  # hourly prices update once/day for next day

    async def get_data(self, location: Location) -> GeoResult:
        today = date.today().isoformat()
        params = {
            "start_date": f"{today}T00:00",
            "end_date": f"{today}T23:59",
            "time_trunc": "hour",
        }
        headers = {"Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(_REE_URL, params=params, headers=headers)
                resp.raise_for_status()
            payload = resp.json()
            included = payload.get("included", [])
            pvpc = next(
                (item for item in included if item.get("type") == "PVPC"),
                None,
            )
            if pvpc is None:
                pvpc = included[0] if included else None

            values = []
            if pvpc:
                attrs = pvpc.get("attributes", {})
                values = attrs.get("values", [])

            prices = [v.get("value") for v in values if v.get("value") is not None]
            return self._ok({
                "currency": "EUR/MWh",
                "prices_today": values,
                "avg": sum(prices) / len(prices) if prices else None,
                "min": min(prices) if prices else None,
                "max": max(prices) if prices else None,
            })
        except Exception as exc:
            logger.warning("ElectricityPriceProvider: %s", exc)
            return self._fail(str(exc))
