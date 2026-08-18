"""
Earthquake alert module for Spain (EMSC FDSN feed).

Configuration via environment variables:
  TERREMOTO_EMSC_URL       — FDSN endpoint (default: seismicportal.eu)
  TERREMOTO_MIN_MAGNITUDE  — minimum magnitude to alert (default: 2.5)
  TERREMOTO_POLL_SECONDS   — polling interval in seconds (default: 300)
  TERREMOTO_MINLAT/MAXLAT/MINLON/MAXLON — bounding box (default: Spain + islands)
"""

import os

import requests

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_NOMINATIM_HEADERS = {"User-Agent": "FuelWeatherBot/1.0 (earthquake alerts)"}

EMSC_URL = os.environ.get(
    "TERREMOTO_EMSC_URL",
    "https://www.seismicportal.eu/fdsnws/event/1/query",
)
MIN_MAGNITUDE = float(os.environ.get("TERREMOTO_MIN_MAGNITUDE", "2.5"))
POLL_SECONDS = int(os.environ.get("TERREMOTO_POLL_SECONDS", "300"))

BBOX = {
    "minlat": float(os.environ.get("TERREMOTO_MINLAT", "27.0")),
    "maxlat": float(os.environ.get("TERREMOTO_MAXLAT", "44.0")),
    "minlon": float(os.environ.get("TERREMOTO_MINLON", "-19.0")),
    "maxlon": float(os.environ.get("TERREMOTO_MAXLON", "5.0")),
}


def reverse_geocode(lat: float, lon: float) -> str | None:
    """Return the nearest settlement name from Nominatim, or None on failure."""
    try:
        resp = requests.get(
            _NOMINATIM_URL,
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 10},
            headers=_NOMINATIM_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        addr = resp.json().get("address", {})
        settlement = (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("hamlet")
            or addr.get("county")
        )
        country = addr.get("country")
        if settlement and country:
            return f"{settlement}, {country}"
        return settlement or country
    except Exception:
        return None


def fetch_recent_quakes() -> list:
    params = {
        "format": "json",
        "minmag": MIN_MAGNITUDE,
        "orderby": "time",
        "limit": 50,
        **BBOX,
    }
    resp = requests.get(EMSC_URL, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json().get("features", [])


def format_message(feature: dict, nearest_place: str | None = None) -> str:
    props = feature["properties"]
    lon, lat, depth = feature["geometry"]["coordinates"]
    mag = props.get("mag")
    magtype = props.get("magtype", "")
    region = props.get("flynn_region", "Unknown region")
    time_str = props.get("time", "")
    maps_url = f"https://www.google.com/maps?q={lat},{lon}"

    location_line = region
    if nearest_place:
        location_line = f"{nearest_place} ({region})"

    return (
        f"\U0001F30D <b>Earthquake detected</b>\n"
        f"Magnitude: <b>{mag} {magtype}</b>\n"
        f"Location: {location_line}\n"
        f"Depth: {depth} km\n"
        f"Time (UTC): {time_str}\n"
        f'<a href="{maps_url}">View on map</a>'
    )
