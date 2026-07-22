"""
Fuel price API helpers — Spain's Ministerio para la Transicion Ecologica feed.
"""

import os
import unicodedata
from math import radians, sin, cos, sqrt, atan2

import ssl

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

BASE_URL = "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes"
STATIONS_BY_PROVINCE_URL = BASE_URL + "/EstacionesTerrestres/FiltroProvincia/{province}"
STATIONS_BY_MUNICIPIO_URL = BASE_URL + "/EstacionesTerrestres/FiltroMunicipio/{municipio}"
MUNICIPIOS_URL = BASE_URL + "/Listados/MunicipiosPorProvincia/{province}"

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FuelPriceBot/1.0)",
    "Accept": "application/json",
}


class _LegacySSLAdapter(HTTPAdapter):
    """Allow servers that close the connection after the TLS handshake (OP_LEGACY_SERVER_CONNECT)."""
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
        kwargs["ssl_context"] = ctx
        super().init_poolmanager(*args, **kwargs)


_session = requests.Session()
_session.mount("https://sedeaplicaciones.minetur.gob.es", _LegacySSLAdapter())


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
    resp = _session.get(url, headers=REQUEST_HEADERS, timeout=20)
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

    resp = _session.get(url, headers=REQUEST_HEADERS, timeout=20)
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


def _maps_link(station: dict) -> str:
    """Return a Google Maps URL for the station — prefer coordinates, fall back to address query."""
    if station.get("lat") and station.get("lon"):
        return f"https://maps.google.com/?q={station['lat']},{station['lon']}"
    query = f"{station.get('address', '')} {station.get('town', '')}".strip()
    if query:
        import urllib.parse
        return f"https://maps.google.com/?q={urllib.parse.quote(query)}"
    return ""


def format_message(
    summary: dict,
    nearest: dict = None,
    municipio_name: str = "",
    province_code: str = "29",
    lang: str = "en",
) -> str:
    from i18n import t

    scope = municipio_name if municipio_name else f"province {province_code}"
    lines = [t(lang, "fuel_header", scope=scope, date=summary["date"]), ""]

    fuel_labels = {
        "Gasoline 95": t(lang, "gasoline_95"),
        "Diesel": t(lang, "diesel"),
    }

    for key, label in fuel_labels.items():
        info = summary["fuels"].get(key, {})
        if info.get("avg") is not None:
            lines.append(t(lang, "fuel_avg", label=label, price=f"{info['avg']:.3f}"))
    lines.append("")

    for key, label in fuel_labels.items():
        info = summary["fuels"].get(key, {})
        c = info.get("cheapest")
        if c:
            lines.append(t(lang, "cheapest", label=label, price=f"{c['price']:.3f}", name=c["name"]))
            if c["address"]:
                link = _maps_link(c)
                addr = f"{c['address']}, {c['town']}"
                lines.append(f"  {addr}" + (f"\n  {link}" if link else ""))

    if nearest:
        lines.append("")
        lines.append(t(lang, "nearest_header", name=nearest["name"], dist=nearest["distance_km"]))
        if nearest["address"]:
            link = _maps_link(nearest)
            addr = f"{nearest['address']}, {nearest['town']}"
            lines.append(f"  {addr}" + (f"\n  {link}" if link else ""))
        if nearest["gasoline_95"] is not None:
            lines.append(f"  {t(lang, 'gasoline_95')}: {nearest['gasoline_95']:.3f} €/L")
        if nearest["diesel"] is not None:
            lines.append(f"  {t(lang, 'diesel')}: {nearest['diesel']:.3f} €/L")

    lines.append("")
    lines.append(t(lang, "stations_reporting", n=summary["station_count"]))
    return "\n".join(lines)
