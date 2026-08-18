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


def format_message(feature: dict) -> str:
    props = feature["properties"]
    lon, lat, depth = feature["geometry"]["coordinates"]
    mag = props.get("mag")
    magtype = props.get("magtype", "")
    place = props.get("flynn_region", "Unknown region")
    time_str = props.get("time", "")
    maps_url = f"https://www.google.com/maps?q={lat},{lon}"

    return (
        f"\U0001F30D <b>Earthquake detected</b>\n"
        f"Magnitude: <b>{mag} {magtype}</b>\n"
        f"Location: {place}\n"
        f"Depth: {depth} km\n"
        f"Time (UTC): {time_str}\n"
        f'<a href="{maps_url}">View on map</a>'
    )
