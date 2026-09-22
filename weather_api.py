"""
Weather helpers using Open-Meteo (no API key required).
Air temperature: api.open-meteo.com
Sea temperature:  marine-api.open-meteo.com
"""

import requests

_AIR_URL = "https://api.open-meteo.com/v1/forecast"
_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

_WIND_DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

WMO_CODES = {
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


_UV_THRESHOLDS = [
    (3, "Low", "Bajo", "Низкий"),
    (6, "Moderate", "Moderado", "Умеренный"),
    (8, "High", "Alto", "Высокий"),
    (11, "Very High", "Muy alto", "Очень высокий"),
    (999, "Extreme", "Extremo", "Экстремальный"),
]
_UV_LANG_IDX = {"en": 1, "es": 2, "ru": 3}

_WMO_ICON = {
    0: "☀️", 1: "☀️", 2: "⛅", 3: "☁️",
    45: "🌫", 48: "🌫",
    51: "🌦", 53: "🌦", 55: "🌧",
    61: "🌦", 63: "🌧", 65: "🌧",
    71: "🌨", 73: "🌨", 75: "🌨",
    80: "🌦", 81: "🌧", 82: "⛈",
    95: "⛈", 96: "⛈", 99: "⛈",
}


def _uv_label(uv: float | None, lang: str) -> str:
    if uv is None:
        return "n/a"
    li = _UV_LANG_IDX.get(lang, 1)
    for threshold, *labels in _UV_THRESHOLDS:
        if uv < threshold:
            return f"{uv:.0f}  ({labels[li - 1]})"
    return f"{uv:.0f}"


def fetch_daily_forecast(lat: float, lon: float) -> dict:
    """Fetch today's daily forecast (air + marine). Returns a flat dict of today's values."""
    air_resp = requests.get(
        _AIR_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": (
                "temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
                "precipitation_sum,precipitation_probability_max,"
                "wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,"
                "uv_index_max,sunrise,sunset,weather_code"
            ),
            "wind_speed_unit": "kmh",
            "timezone": "auto",
        },
        timeout=15,
    )
    air_resp.raise_for_status()
    d = air_resp.json().get("daily", {})

    def _v(key):
        vals = d.get(key, [])
        return vals[0] if vals else None

    result = {
        "temp_max": _v("temperature_2m_max"),
        "temp_min": _v("temperature_2m_min"),
        "feels_max": _v("apparent_temperature_max"),
        "precip_mm": _v("precipitation_sum"),
        "precip_prob": _v("precipitation_probability_max"),
        "wind_max": _v("wind_speed_10m_max"),
        "gusts_max": _v("wind_gusts_10m_max"),
        "wind_dir": _v("wind_direction_10m_dominant"),
        "uv_max": _v("uv_index_max"),
        "sunrise": _v("sunrise"),
        "sunset": _v("sunset"),
        "weather_code": _v("weather_code"),
        "wave_height_max": None,
    }

    try:
        marine_resp = requests.get(
            _MARINE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "wave_height_max",
                "timezone": "auto",
            },
            timeout=15,
        )
        marine_resp.raise_for_status()
        wh = marine_resp.json().get("daily", {}).get("wave_height_max", [])
        result["wave_height_max"] = wh[0] if wh else None
    except Exception:
        pass

    return result


def format_daily_forecast_message(forecast: dict, lang: str = "en") -> str:
    from i18n import t

    codes = WMO_CODES.get(lang, WMO_CODES["en"])
    condition = codes.get(forecast.get("weather_code"), "")

    def _temp(v):
        return f"{v:.0f}°C" if v is not None else "n/a"

    def _time(ts):
        return ts[11:16] if ts and len(ts) >= 16 else (ts or "n/a")

    wind_parts = []
    if forecast.get("wind_max") is not None:
        wind_parts.append(f"max {forecast['wind_max']:.0f} km/h")
    if forecast.get("gusts_max") is not None:
        wind_parts.append(f"gusts {forecast['gusts_max']:.0f} km/h")
    if forecast.get("wind_dir") is not None:
        wind_parts.append(_wind_direction_label(forecast["wind_dir"]))
    wind_str = "  ".join(wind_parts) or "n/a"

    rain_parts = []
    if forecast.get("precip_prob") is not None:
        rain_parts.append(f"{forecast['precip_prob']:.0f}%")
    if forecast.get("precip_mm") is not None:
        rain_parts.append(f"{forecast['precip_mm']:.1f} mm")
    rain_str = "  /  ".join(rain_parts) or "n/a"

    lines = [t(lang, "daily_forecast_header"), ""]
    if condition:
        lines += [f"☁️  {condition}", ""]
    lines += [
        f"🌡  {t(lang, 'daily_temp')}:  {_temp(forecast.get('temp_min'))}–{_temp(forecast.get('temp_max'))}  (feels up to {_temp(forecast.get('feels_max'))})",
        f"🌧  {t(lang, 'daily_rain')}:   {rain_str}",
        f"🌬  {t(lang, 'daily_wind')}:   {wind_str}",
        f"☀️  {t(lang, 'daily_uv')}:     {_uv_label(forecast.get('uv_max'), lang)}",
        f"🌅  {t(lang, 'daily_sunrise')}: {_time(forecast.get('sunrise'))}  ·  {t(lang, 'daily_sunset')}: {_time(forecast.get('sunset'))}",
    ]
    if forecast.get("wave_height_max") is not None:
        lines.append(f"🌊  {t(lang, 'daily_waves')}:  max {forecast['wave_height_max']:.1f} m")
    return "\n".join(lines)


def fetch_hourly_forecast(lat: float, lon: float) -> list:
    """Fetch today's hourly forecast. Returns list of 24 dicts (local timezone)."""
    resp = requests.get(
        _AIR_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,precipitation_probability,weather_code,wind_speed_10m,wind_direction_10m",
            "wind_speed_unit": "kmh",
            "timezone": "auto",
            "forecast_days": 1,
        },
        timeout=15,
    )
    resp.raise_for_status()
    h = resp.json().get("hourly", {})
    times = h.get("time", [])
    return [
        {
            "time": times[i][11:16],
            "temp": h["temperature_2m"][i],
            "precip_prob": h["precipitation_probability"][i],
            "weather_code": h["weather_code"][i],
            "wind_speed": h["wind_speed_10m"][i],
            "wind_dir": h["wind_direction_10m"][i],
        }
        for i in range(len(times))
    ]


def format_hourly_forecast_message(hours: list, lang: str = "en") -> str:
    from i18n import t

    lines = [t(lang, "hourly_forecast_header"), ""]
    for h in hours:
        icon = _WMO_ICON.get(h["weather_code"], "❓")
        temp = f"{h['temp']:.0f}°" if h["temp"] is not None else "?°"
        prob = f"{h['precip_prob']:.0f}%" if h["precip_prob"] is not None else "?"
        wind = f"{h['wind_speed']:.0f}" if h["wind_speed"] is not None else "?"
        wdir = _wind_direction_label(h["wind_dir"]) if h["wind_dir"] is not None else ""
        lines.append(f"{h['time']}  {temp:>4}  {icon}  💧{prob:>3}  💨{wind:>3} {wdir}")
    return "\n".join(lines)


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

    codes = WMO_CODES.get(lang, WMO_CODES["en"])
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
