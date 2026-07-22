"""
Fuel price API helpers — Spain's Ministerio para la Transicion Ecologica feed.
"""

import os
import unicodedata
from math import radians, sin, cos, sqrt, atan2

import requests

BASE_URL = "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes"
STATIONS_BY_PROVINCE_URL = BASE_URL + "/EstacionesTerrestres/FiltroProvincia/{province}"
STATIONS_BY_MUNICIPIO_URL = BASE_URL + "/EstacionesTerrestres/FiltroMunicipio/{municipio}"
MUNICIPIOS_URL = BASE_URL + "/Listados/MunicipiosPorProvincia/{province}"

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FuelPriceBot/1.0)",
    "Accept": "application/json",
}


def _parse_number(value):
    """Convert Spanish-formatted decimal strings (e.g. '1,359') to float."""
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _normalize(text):
    """Uppercase + strip accents, for tolerant municipality-name matching."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper().strip()


def get_municipio_id(province_code: str, municipio_name: str) -> str:
    """Look up the Ministry's internal municipality ID by name."""
    url = MUNICIPIOS_URL.format(province=province_code)
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=20)
    resp.raise_for_status()
    municipios = resp.json()

    target = _normalize(municipio_name)
    for m in municipios:
        name = m.get("Municipio") or m.get("municipio") or ""
        if _normalize(name) == target:
            municipio_id = m.get("IDMunicipio") or m.get("IDMunicipio".upper())
            if municipio_id:
                return municipio_id

    raise ValueError(
        f"Municipality '{municipio_name}' not found in province {province_code}."
    )


def _station_summary(raw: dict) -> dict:
    return {
        "name": (raw.get("Rótulo") or "").strip(),
        "address": (raw.get("Dirección") or "").strip(),
        "town": (raw.get("Municipio") or "").strip(),
        "postal_code": (raw.get("C.P.") or "").strip(),
        "lat": _parse_number(raw.get("Latitud")),
        "lon": _parse_number(raw.get("Longitud (WGS84)")),
        "gasoline_95": _parse_number(raw.get("Precio Gasolina 95 E5")),
        "diesel": _parse_number(raw.get("Precio Gasoleo A")),
    }


def fetch_stations(province_code: str, municipio_name: str = "") -> dict:
    """Fetch current station list + prices for the given province/municipality."""
    if municipio_name:
        municipio_id = get_municipio_id(province_code, municipio_name)
        url = STATIONS_BY_MUNICIPIO_URL.format(municipio=municipio_id)
    else:
        url = STATIONS_BY_PROVINCE_URL.format(province=province_code)

    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=20)
    resp.raise_for_status()
    payload = resp.json()

    raw_stations = payload.get("ListaEESSPrecio", [])
    if not raw_stations:
        raise ValueError("No stations returned from the API.")

    return {
        "date": payload.get("Fecha"),
        "stations": [_station_summary(s) for s in raw_stations],
    }


def summarize(data: dict) -> dict:
    fuels = {"Gasoline 95": "gasoline_95", "Diesel": "diesel"}
    summary = {"date": data["date"], "station_count": len(data["stations"]), "fuels": {}}

    for label, field in fuels.items():
        prices = []
        cheapest = None
        for st in data["stations"]:
            price = st[field]
            if price is None:
                continue
            prices.append(price)
            if cheapest is None or price < cheapest["price"]:
                cheapest = {"price": price, **st}
        summary["fuels"][label] = {
            "avg": sum(prices) / len(prices) if prices else None,
            "cheapest": cheapest,
        }
    return summary


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def geocode_address(address: str, api_key: str):
    """Convert a home address to (lat, lon) using Google's Geocoding API."""
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": address, "key": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "OK" or not payload.get("results"):
        return None
    loc = payload["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def find_nearest_station(stations, home_lat, home_lon):
    best = None
    for st in stations:
        if st["lat"] is None or st["lon"] is None:
            continue
        dist = haversine_km(home_lat, home_lon, st["lat"], st["lon"])
        if best is None or dist < best["distance_km"]:
            best = {**st, "distance_km": dist}
    return best


def format_message(summary: dict, nearest: dict = None, municipio_name: str = "", province_code: str = "29") -> str:
    scope = municipio_name if municipio_name else f"province {province_code}"
    lines = [f"⛽ Fuel prices — {scope} ({summary['date']})", ""]

    for label, info in summary["fuels"].items():
        if info["avg"] is not None:
            lines.append(f"{label} (avg): {info['avg']:.3f} €/L")
    lines.append("")

    for label, info in summary["fuels"].items():
        c = info["cheapest"]
        if c:
            lines.append(f"Cheapest {label}: {c['price']:.3f} €/L — {c['name']}")
            if c["address"]:
                lines.append(f"  {c['address']}, {c['town']}")

    if nearest:
        lines.append("")
        lines.append(f"📍 Nearest station to you: {nearest['name']} ({nearest['distance_km']:.1f} km)")
        if nearest["address"]:
            lines.append(f"  {nearest['address']}, {nearest['town']}")
        if nearest["gasoline_95"] is not None:
            lines.append(f"  Gasoline 95: {nearest['gasoline_95']:.3f} €/L")
        if nearest["diesel"] is not None:
            lines.append(f"  Diesel: {nearest['diesel']:.3f} €/L")

    lines.append("")
    lines.append(f"({summary['station_count']} stations reporting)")
    return "\n".join(lines)
