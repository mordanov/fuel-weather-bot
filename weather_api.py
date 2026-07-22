"""
Weather helpers using Open-Meteo (no API key required).
Air temperature: api.open-meteo.com
Sea temperature:  marine-api.open-meteo.com
"""

import requests

_AIR_URL = "https://api.open-meteo.com/v1/forecast"
_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

_WIND_DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

_WMO_CODES = {
    "en": {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Icy fog",
        51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
        61: "Light rain", 63: "Rain", 65: "Heavy rain",
        71: "Light snow", 73: "Snow", 75: "Heavy snow",
        80: "Light showers", 81: "Showers", 82: "Heavy showers",
        95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Heavy thunderstorm with hail",
    },
    "es": {
        0: "Cielo despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado", 3: "Nublado",
        45: "Niebla", 48: "Niebla helada",
        51: "Llovizna ligera", 53: "Llovizna", 55: "Llovizna intensa",
        61: "Lluvia ligera", 63: "Lluvia", 65: "Lluvia intensa",
        71: "Nieve ligera", 73: "Nieve", 75: "Nieve intensa",
        80: "Chubascos ligeros", 81: "Chubascos", 82: "Chubascos fuertes",
        95: "Tormenta", 96: "Tormenta con granizo", 99: "Tormenta fuerte con granizo",
    },
    "ru": {
        0: "Ясно", 1: "Преимущественно ясно", 2: "Переменная облачность", 3: "Пасмурно",
        45: "Туман", 48: "Ледяной туман",
        51: "Морось слабая", 53: "Морось", 55: "Морось сильная",
        61: "Дождь слабый", 63: "Дождь", 65: "Дождь сильный",
        71: "Снег слабый", 73: "Снег", 75: "Снег сильный",
        80: "Ливень слабый", 81: "Ливень", 82: "Ливень сильный",
        95: "Гроза", 96: "Гроза с градом", 99: "Сильная гроза с градом",
    },
}


def _wind_direction_label(degrees: float) -> str:
    return _WIND_DIRS[round(degrees / 45) % 8]


def fetch_weather(lat: float, lon: float) -> dict:
    """Fetch current air and sea conditions. Returns a dict with all fields."""
    air_resp = requests.get(
        _AIR_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,wind_speed_10m,wind_direction_10m,weather_code",
            "wind_speed_unit": "kmh",
        },
        timeout=15,
    )
    air_resp.raise_for_status()
    air = air_resp.json().get("current", {})

    marine_resp = requests.get(
        _MARINE_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "sea_surface_temperature,wave_height,wave_direction",
        },
        timeout=15,
    )
    marine_resp.raise_for_status()
    marine = marine_resp.json().get("current", {})

    return {
        "temperature": air.get("temperature_2m"),
        "feels_like": air.get("apparent_temperature"),
        "wind_speed": air.get("wind_speed_10m"),
        "wind_direction": air.get("wind_direction_10m"),
        "weather_code": air.get("weather_code"),
        "sea_temperature": marine.get("sea_surface_temperature"),
        "wave_height": marine.get("wave_height"),
        "wave_direction": marine.get("wave_direction"),
    }


def format_weather_message(weather: dict, lat: float, lon: float, lang: str = "en") -> str:
    from i18n import t

    def fmt_temp(val):
        return f"{val:.1f}°C" if val is not None else "n/a"

    def fmt_float(val, unit):
        return f"{val:.1f} {unit}" if val is not None else "n/a"

    codes = _WMO_CODES.get(lang, _WMO_CODES["en"])
    condition = codes.get(weather.get("weather_code"), "Unknown")

    wind_label = ""
    if weather["wind_speed"] is not None and weather["wind_direction"] is not None:
        wind_label = (
            f"{weather['wind_speed']:.0f} km/h "
            f"{_wind_direction_label(weather['wind_direction'])}"
        )
    else:
        wind_label = "n/a"

    wave_label = ""
    if weather["wave_height"] is not None and weather["wave_direction"] is not None:
        wave_label = (
            f"{weather['wave_height']:.1f} m "
            f"{_wind_direction_label(weather['wave_direction'])}"
        )
    elif weather["wave_height"] is not None:
        wave_label = fmt_float(weather["wave_height"], "m")
    else:
        wave_label = "n/a"

    lines = [
        t(lang, "weather_header", lat=lat, lon=lon),
        "",
        f"☁️  {condition}",
        f"🌡  Air: {fmt_temp(weather['temperature'])} (feels like {fmt_temp(weather['feels_like'])})",
        f"🌬  Wind: {wind_label}",
        f"🌊 Sea: {fmt_temp(weather['sea_temperature'])}",
        f"〰️  Waves: {wave_label}",
    ]
    return "\n".join(lines)
