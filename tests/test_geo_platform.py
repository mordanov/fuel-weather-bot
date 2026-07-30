"""
Tests for the geo-information platform.

Coverage:
  - GeoCache (get/set/expiry/len)
  - GeoDataAggregator (success, timeout, provider error, cache hit)
  - WeatherProvider
  - SeaProvider
  - AirQualityProvider
  - PollenProvider
  - ElectricityPriceProvider
  - FuelProvider (via executor, wraps CompositeFuelProvider)
  - EVChargingProvider
  - ForestFireProvider
  - ParkingProvider

All external HTTP calls are mocked with unittest.mock or pytest-httpx.
"""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from geo.cache import GeoCache
from geo.models import GeoResult, Location
from geo.aggregator import GeoDataAggregator
from geo.provider import GeoDataProvider
from geo.providers.weather import WeatherProvider
from geo.providers.sea import SeaProvider
from geo.providers.air_quality import AirQualityProvider, aqi_label
from geo.providers.pollen import PollenProvider, pollen_level_label
from geo.providers.electricity import ElectricityPriceProvider
from geo.providers.fuel import FuelProvider
from geo.providers.ev_charging import EVChargingProvider
from geo.providers.forest_fire import ForestFireProvider
from geo.providers.parking import ParkingProvider

MALAGA = Location(lat=36.7213, lon=-4.4214, city="Málaga", province="Málaga")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_httpx_get(json_body: dict, status_code: int = 200):
    """Return an async context manager that yields a fake httpx response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_body
    mock_resp.raise_for_status = MagicMock()
    mock_resp.text = ""

    class _AsyncCtx:
        async def __aenter__(self_inner):
            return mock_resp
        async def __aexit__(self_inner, *args):
            pass
        async def get(self_inner, *args, **kwargs):
            return mock_resp
        async def post(self_inner, *args, **kwargs):
            return mock_resp

    return _AsyncCtx()


def _patch_httpx(json_body: dict, status_code: int = 200):
    """Patch httpx.AsyncClient to return a fake response."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_body
    mock_resp.raise_for_status = MagicMock()
    mock_resp.text = ""
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return patch("httpx.AsyncClient", return_value=mock_client), mock_client, mock_resp


# ---------------------------------------------------------------------------
# GeoCache tests
# ---------------------------------------------------------------------------

class TestGeoCache:
    def test_set_and_get(self):
        cache = GeoCache()
        result = GeoResult(provider="test", timestamp=datetime.now(timezone.utc), data={"x": 1})
        cache.set("k", result, ttl=60)
        assert cache.get("k") is result

    def test_miss_returns_none(self):
        cache = GeoCache()
        assert cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self):
        cache = GeoCache()
        result = GeoResult(provider="test", timestamp=datetime.now(timezone.utc), data={})
        cache.set("k", result, ttl=0)
        time.sleep(0.01)
        assert cache.get("k") is None

    def test_len_counts_live_entries(self):
        cache = GeoCache()
        cache.set("a", object(), ttl=60)
        cache.set("b", object(), ttl=0)
        time.sleep(0.01)
        assert len(cache) == 1

    def test_clear(self):
        cache = GeoCache()
        cache.set("a", object(), ttl=60)
        cache.clear()
        assert len(cache) == 0

    def test_invalidate(self):
        cache = GeoCache()
        cache.set("a", object(), ttl=60)
        cache.invalidate("a")
        assert cache.get("a") is None


# ---------------------------------------------------------------------------
# GeoDataAggregator tests
# ---------------------------------------------------------------------------

class _OkProvider(GeoDataProvider):
    provider_name = "ok"
    cache_ttl = 60

    async def get_data(self, location: Location) -> GeoResult:
        return self._ok({"value": 42})


class _FailProvider(GeoDataProvider):
    provider_name = "fail"
    cache_ttl = 60

    async def get_data(self, location: Location) -> GeoResult:
        return self._fail("always fails")


class _SlowProvider(GeoDataProvider):
    provider_name = "slow"
    cache_ttl = 60

    async def get_data(self, location: Location) -> GeoResult:
        await asyncio.sleep(999)
        return self._ok({})


class TestGeoDataAggregator:
    @pytest.mark.asyncio
    async def test_gather_success(self):
        agg = GeoDataAggregator([_OkProvider()], default_timeout=5.0)
        results = await agg.gather(MALAGA)
        assert "ok" in results
        assert results["ok"].ok
        assert results["ok"].data["value"] == 42

    @pytest.mark.asyncio
    async def test_gather_failure_doesnt_raise(self):
        agg = GeoDataAggregator([_FailProvider()], default_timeout=5.0)
        results = await agg.gather(MALAGA)
        assert "fail" in results
        assert not results["fail"].ok

    @pytest.mark.asyncio
    async def test_timeout_returns_failure(self):
        agg = GeoDataAggregator([_SlowProvider()], default_timeout=0.05)
        results = await agg.gather(MALAGA)
        assert not results["slow"].ok
        assert "timed out" in results["slow"].error

    @pytest.mark.asyncio
    async def test_cache_hit_on_second_call(self):
        provider = _OkProvider()
        agg = GeoDataAggregator([provider], default_timeout=5.0)
        r1 = await agg.get("ok", MALAGA)
        assert r1.source == "live"
        r2 = await agg.get("ok", MALAGA)
        assert r2.source == "cache"

    @pytest.mark.asyncio
    async def test_include_filter(self):
        agg = GeoDataAggregator([_OkProvider(), _FailProvider()], default_timeout=5.0)
        results = await agg.gather(MALAGA, include=["ok"])
        assert "ok" in results
        assert "fail" not in results

    @pytest.mark.asyncio
    async def test_unknown_provider_returns_failure(self):
        agg = GeoDataAggregator([], default_timeout=5.0)
        result = await agg.get("nonexistent", MALAGA)
        assert not result.ok


# ---------------------------------------------------------------------------
# WeatherProvider tests
# ---------------------------------------------------------------------------

class TestWeatherProvider:
    @pytest.mark.asyncio
    async def test_ok_response(self):
        body = {
            "current": {
                "temperature_2m": 24.5,
                "apparent_temperature": 23.0,
                "wind_speed_10m": 15.0,
                "wind_direction_10m": 270,
                "weather_code": 2,
                "relative_humidity_2m": 60,
            }
        }
        patch_ctx, mock_client, _ = _patch_httpx(body)
        with patch_ctx:
            provider = WeatherProvider()
            result = await provider.get_data(MALAGA)
        assert result.ok
        assert result.data["temperature"] == 24.5
        assert result.data["humidity"] == 60

    @pytest.mark.asyncio
    async def test_http_error_returns_failure(self):
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_cls.return_value = mock_client
            provider = WeatherProvider()
            result = await provider.get_data(MALAGA)
        assert not result.ok


# ---------------------------------------------------------------------------
# SeaProvider tests
# ---------------------------------------------------------------------------

class TestSeaProvider:
    @pytest.mark.asyncio
    async def test_ok_response(self):
        body = {
            "current": {
                "sea_surface_temperature": 22.1,
                "wave_height": 0.5,
                "wave_direction": 180,
                "wave_period": 8.0,
            }
        }
        patch_ctx, _, _ = _patch_httpx(body)
        with patch_ctx:
            result = await SeaProvider().get_data(MALAGA)
        assert result.ok
        assert result.data["sea_temperature"] == 22.1
        assert result.data["wave_height"] == 0.5


# ---------------------------------------------------------------------------
# AirQualityProvider tests
# ---------------------------------------------------------------------------

class TestAirQualityProvider:
    @pytest.mark.asyncio
    async def test_ok_response(self):
        body = {
            "current": {
                "pm2_5": 5.2,
                "pm10": 12.0,
                "nitrogen_dioxide": 8.1,
                "ozone": 60.0,
                "european_aqi": 1,
            }
        }
        patch_ctx, _, _ = _patch_httpx(body)
        with patch_ctx:
            result = await AirQualityProvider().get_data(MALAGA)
        assert result.ok
        assert result.data["european_aqi"] == 1

    def test_aqi_label(self):
        assert aqi_label(1, "en") == "Good"
        assert aqi_label(4, "es") == "Mala"
        assert aqi_label(None, "en") == "n/a"


# ---------------------------------------------------------------------------
# PollenProvider tests
# ---------------------------------------------------------------------------

class TestPollenProvider:
    @pytest.mark.asyncio
    async def test_ok_response(self):
        body = {
            "current": {
                "grass_pollen": 30.0,
                "olive_pollen": 120.0,
                "birch_pollen": 5.0,
                "mugwort_pollen": 2.0,
                "alder_pollen": 0.0,
                "ragweed_pollen": 15.0,
            }
        }
        patch_ctx, _, _ = _patch_httpx(body)
        with patch_ctx:
            result = await PollenProvider().get_data(MALAGA)
        assert result.ok
        assert result.data["olive_pollen"] == 120.0

    def test_pollen_level_labels(self):
        assert pollen_level_label(5) == "Low"
        assert pollen_level_label(30) == "Moderate"
        assert pollen_level_label(100) == "High"
        assert pollen_level_label(300) == "Very High"
        assert pollen_level_label(None) == "n/a"


# ---------------------------------------------------------------------------
# ElectricityPriceProvider tests
# ---------------------------------------------------------------------------

class TestElectricityPriceProvider:
    @pytest.mark.asyncio
    async def test_ok_response(self):
        values = [{"datetime": "2026-07-26T00:00", "value": 85.0}] * 24
        body = {
            "included": [
                {"type": "PVPC", "attributes": {"values": values}}
            ]
        }
        patch_ctx, _, _ = _patch_httpx(body)
        with patch_ctx:
            result = await ElectricityPriceProvider().get_data(MALAGA)
        assert result.ok
        assert result.data["avg"] == 85.0
        assert result.data["currency"] == "EUR/MWh"

    @pytest.mark.asyncio
    async def test_empty_response_gives_none_avg(self):
        body = {"included": []}
        patch_ctx, _, _ = _patch_httpx(body)
        with patch_ctx:
            result = await ElectricityPriceProvider().get_data(MALAGA)
        assert result.ok
        assert result.data["avg"] is None


# ---------------------------------------------------------------------------
# FuelProvider tests
# ---------------------------------------------------------------------------

class TestFuelProvider:
    @pytest.mark.asyncio
    async def test_wraps_composite_provider(self):
        mock_data = {
            "date": "26/07/2026",
            "stations": [{"name": "REPSOL", "gasoline_95": 1.65, "diesel": 1.49,
                           "address": "", "town": "", "postal_code": "", "lat": None, "lon": None}],
        }
        with patch("fuel_providers.CompositeFuelProvider") as MockComposite:
            instance = MockComposite.return_value
            instance.fetch.return_value = mock_data
            provider = FuelProvider("29", "MALAGA")
            result = await provider.get_data(MALAGA)
        assert result.ok
        assert result.data["stations"][0]["name"] == "REPSOL"

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self):
        with patch("fuel_providers.CompositeFuelProvider") as MockComposite:
            instance = MockComposite.return_value
            instance.fetch.side_effect = RuntimeError("all providers failed")
            provider = FuelProvider("29", "MALAGA")
            result = await provider.get_data(MALAGA)
        assert not result.ok
        assert "all providers failed" in result.error


# ---------------------------------------------------------------------------
# EVChargingProvider tests
# ---------------------------------------------------------------------------

class TestEVChargingProvider:
    @pytest.mark.asyncio
    async def test_ok_response(self):
        body = [
            {
                "AddressInfo": {
                    "Title": "ChargePoint",
                    "AddressLine1": "Calle Mayor 1",
                    "Latitude": 36.72,
                    "Longitude": -4.42,
                    "Distance": 1.2,
                },
                "NumberOfPoints": 2,
                "Connections": [{"PowerKW": 22.0}],
                "OperatorInfo": {"Title": "ChargePoint Inc"},
            }
        ]
        patch_ctx, _, _ = _patch_httpx(body)
        with patch_ctx, patch.dict("os.environ", {"OPENCHARGEMAP_API_KEY": "testkey"}):
            result = await EVChargingProvider(radius_km=5).get_data(MALAGA)
        assert result.ok
        assert result.data["count"] == 1
        assert result.data["stations"][0]["max_kw"] == 22.0


# ---------------------------------------------------------------------------
# ForestFireProvider tests
# ---------------------------------------------------------------------------

class TestForestFireProvider:
    @pytest.mark.asyncio
    async def test_no_fires(self):
        with patch("httpx.AsyncClient") as mock_cls, patch.dict("os.environ", {"FIRMS_MAP_KEY": "testkey"}):
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.text = "latitude,longitude,bright_ti4,frp,acq_date,acq_time\n"
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            result = await ForestFireProvider(radius_km=50).get_data(MALAGA)
        assert result.ok
        assert result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_nearby_fire_included(self):
        csv_data = (
            "latitude,longitude,bright_ti4,frp,acq_date,acq_time\n"
            "36.80,-4.40,310.5,25.3,2026-07-26,1230\n"  # ~9 km from MALAGA
        )
        with patch("httpx.AsyncClient") as mock_cls, patch.dict("os.environ", {"FIRMS_MAP_KEY": "testkey"}):
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.text = csv_data
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            result = await ForestFireProvider(radius_km=50).get_data(MALAGA)
        assert result.ok
        assert result.data["count"] == 1
        assert result.data["fires"][0]["distance_km"] < 50


# ---------------------------------------------------------------------------
# ParkingProvider tests
# ---------------------------------------------------------------------------

class TestParkingProvider:
    @pytest.mark.asyncio
    async def test_ok_response(self):
        body = {
            "elements": [
                {
                    "type": "node",
                    "lat": 36.722,
                    "lon": -4.421,
                    "tags": {"name": "Parking Alameda", "capacity": "200", "fee": "yes"},
                }
            ]
        }
        patch_ctx, _, _ = _patch_httpx(body)
        with patch_ctx:
            result = await ParkingProvider().get_data(MALAGA)
        assert result.ok
        assert result.data["count"] == 1
        assert result.data["lots"][0]["capacity"] == "200"
