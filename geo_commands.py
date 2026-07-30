"""
Telegram command handlers for the geo-information platform.

Commands registered here:
  /fuel         — current fuel prices (replaces /check for geo-aware use)
  /weather      — air conditions
  /sea          — sea temperature and waves
  /air          — air quality index
  /pollen       — pollen levels
  /electricity  — electricity spot prices (REE)
  /ev           — EV charging stations nearby
  /fire         — active forest fires nearby
  /parking      — parking lots nearby
  /location     — show current location used for geo commands
  /around       — combined summary of all providers

All commands use the user's /home coordinates, falling back to DEFAULT_LAT/DEFAULT_LON.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from html import escape

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

import i18n
import db
from geo.aggregator import GeoDataAggregator
from geo.models import Location, GeoResult
from geo.providers.air_quality import AirQualityProvider, aqi_label
from geo.providers.electricity import ElectricityPriceProvider
from geo.providers.ev_charging import EVChargingProvider
from geo.providers.forest_fire import ForestFireProvider
from geo.providers.fuel import FuelProvider
from geo.providers.parking import ParkingProvider
from geo.providers.pollen import PollenProvider, pollen_level_label
from geo.providers.sea import SeaProvider
from geo.providers.weather import WeatherProvider

logger = logging.getLogger(__name__)

DEFAULT_LAT = float(os.environ.get("DEFAULT_LAT", "36.7213"))
DEFAULT_LON = float(os.environ.get("DEFAULT_LON", "-4.4214"))
PROVINCE_CODE = os.environ.get("PROVINCE_CODE", "29")
MUNICIPIO_NAME = os.environ.get("MUNICIPIO_NAME", "")
SEARCH_RADIUS_KM = int(os.environ.get("SEARCH_RADIUS_KM", "25"))

# Wind direction helper
_WIND_DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _wind_dir(degrees: float | None) -> str:
    if degrees is None:
        return ""
    return _WIND_DIRS[round(degrees / 45) % 8]


def _fmt_temp(val: float | None) -> str:
    return f"{val:.1f}°C" if val is not None else "n/a"


def _fmt_float(val: float | None, unit: str = "") -> str:
    if val is None:
        return "n/a"
    return f"{val:.1f} {unit}".strip()


# ---------------------------------------------------------------------------
# Shared aggregator (module-level singleton, lazily initialized in build_aggregator)
# ---------------------------------------------------------------------------

_aggregator: Optional[GeoDataAggregator] = None


def build_aggregator() -> GeoDataAggregator:
    global _aggregator
    if _aggregator is not None:
        return _aggregator

    enabled = os.environ.get

    providers = []

    if enabled("ENABLE_FUEL_PROVIDER", "1") not in ("0", "false", "no"):
        providers.append(FuelProvider(PROVINCE_CODE, MUNICIPIO_NAME))
    if enabled("ENABLE_WEATHER_PROVIDER", "1") not in ("0", "false", "no"):
        providers.append(WeatherProvider())
    if enabled("ENABLE_SEA_PROVIDER", "1") not in ("0", "false", "no"):
        providers.append(SeaProvider())
    if enabled("ENABLE_AIR_PROVIDER", "1") not in ("0", "false", "no"):
        providers.append(AirQualityProvider())
    if enabled("ENABLE_POLLEN_PROVIDER", "1") not in ("0", "false", "no"):
        providers.append(PollenProvider())
    if enabled("ENABLE_ELECTRICITY_PROVIDER", "1") not in ("0", "false", "no"):
        providers.append(ElectricityPriceProvider())
    if enabled("ENABLE_EV_PROVIDER", "1") not in ("0", "false", "no"):
        providers.append(EVChargingProvider(radius_km=SEARCH_RADIUS_KM))
    if enabled("ENABLE_FIRE_PROVIDER", "1") not in ("0", "false", "no"):
        providers.append(ForestFireProvider(radius_km=SEARCH_RADIUS_KM))
    if enabled("ENABLE_PARKING_PROVIDER", "1") not in ("0", "false", "no"):
        providers.append(ParkingProvider(radius_m=SEARCH_RADIUS_KM * 1000 // 5))

    _aggregator = GeoDataAggregator(providers, default_timeout=12.0)
    return _aggregator


def _user_location(user: dict) -> Location:
    lat = user["home_lat"] if user["home_lat"] is not None else DEFAULT_LAT
    lon = user["home_lon"] if user["home_lon"] is not None else DEFAULT_LON
    return Location(lat=lat, lon=lon)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _format_weather(result: GeoResult, lang: str) -> str:
    if not result.ok:
        return i18n.t(lang, "weather_error", e=result.error)
    d = result.data
    wind = ""
    if d.get("wind_speed") is not None:
        wind = f"{d['wind_speed']:.0f} km/h {_wind_dir(d.get('wind_direction'))}"
    from weather_api import _WMO_CODES
    codes = _WMO_CODES.get(lang, _WMO_CODES["en"])
    condition = codes.get(d.get("weather_code"), "")
    humidity = d.get("humidity")
    lines = [
        i18n.t(lang, "weather_header", lat=0, lon=0).split("(")[0].strip(),
        f"☁️  {condition}" if condition else "",
        f"🌡  {i18n.t(lang, 'geo_air_temp')}: {_fmt_temp(d.get('temperature'))} (feels {_fmt_temp(d.get('feels_like'))})",
        f"🌬  {i18n.t(lang, 'geo_wind')}: {wind or 'n/a'}",
        f"💧 {i18n.t(lang, 'geo_humidity')}: {humidity:.0f}%" if humidity is not None else "",
    ]
    return "\n".join(l for l in lines if l)


def _format_sea(result: GeoResult, lang: str) -> str:
    if not result.ok:
        return i18n.t(lang, "geo_error", provider="sea", e=result.error)
    d = result.data
    wave = ""
    if d.get("wave_height") is not None:
        wave = f"{d['wave_height']:.1f} m {_wind_dir(d.get('wave_direction'))}"
        if d.get("wave_period") is not None:
            wave += f" ({d['wave_period']:.0f}s)"
    lines = [
        f"🌊 {i18n.t(lang, 'geo_sea_header')}",
        f"🌡  {i18n.t(lang, 'geo_sea_temp')}: {_fmt_temp(d.get('sea_temperature'))}",
        f"〰️  {i18n.t(lang, 'geo_waves')}: {wave or 'n/a'}",
    ]
    return "\n".join(lines)


def _format_air(result: GeoResult, lang: str) -> str:
    if not result.ok:
        return i18n.t(lang, "geo_error", provider="air quality", e=result.error)
    d = result.data
    aqi = d.get("european_aqi")
    lines = [
        f"🍃 {i18n.t(lang, 'geo_air_header')}",
        f"📊 {i18n.t(lang, 'geo_aqi')}: {aqi_label(aqi, lang)} ({aqi})" if aqi else f"📊 AQI: n/a",
        f"  PM2.5: {_fmt_float(d.get('pm2_5'), 'μg/m³')}",
        f"  PM10:  {_fmt_float(d.get('pm10'), 'μg/m³')}",
        f"  NO₂:   {_fmt_float(d.get('no2'), 'μg/m³')}",
        f"  O₃:    {_fmt_float(d.get('o3'), 'μg/m³')}",
    ]
    return "\n".join(lines)


def _format_pollen(result: GeoResult, lang: str) -> str:
    if not result.ok:
        return i18n.t(lang, "geo_error", provider="pollen", e=result.error)
    d = result.data
    fields = [
        ("🌿 Grass", d.get("grass_pollen")),
        ("🌳 Olive", d.get("olive_pollen")),
        ("🌲 Birch", d.get("birch_pollen")),
        ("🌾 Ragweed", d.get("ragweed_pollen")),
        ("🍀 Alder", d.get("alder_pollen")),
        ("🌻 Mugwort", d.get("mugwort_pollen")),
    ]
    lines = [f"🤧 {i18n.t(lang, 'geo_pollen_header')}"]
    for name, val in fields:
        if val is not None:
            lines.append(f"  {name}: {pollen_level_label(val)} ({_fmt_float(val, 'grains/m³')})")
    return "\n".join(lines)


def _format_electricity(result: GeoResult, lang: str) -> str:
    if not result.ok:
        return i18n.t(lang, "geo_error", provider="electricity", e=result.error)
    d = result.data
    avg = d.get("avg")
    mn = d.get("min")
    mx = d.get("max")
    lines = [
        f"⚡ {i18n.t(lang, 'geo_electricity_header')}",
        f"  {i18n.t(lang, 'geo_avg')}: {avg:.2f} €/MWh" if avg else "  avg: n/a",
        f"  {i18n.t(lang, 'geo_min')}: {mn:.2f}   {i18n.t(lang, 'geo_max')}: {mx:.2f}" if mn and mx else "",
    ]
    return "\n".join(l for l in lines if l)


def _maps_link(lat: float | None, lon: float | None, label: str) -> str:
    if lat is None or lon is None:
        return escape(label)
    url = f"https://maps.google.com/?q={lat},{lon}"
    return f'<a href="{url}">{escape(label)}</a>'


def _format_ev(result: GeoResult, lang: str) -> str:
    if not result.ok:
        return escape(i18n.t(lang, "geo_error", provider="EV charging", e=result.error))
    d = result.data
    stations = d.get("stations", [])
    lines = [escape(f"🔌 {i18n.t(lang, 'geo_ev_header', count=len(stations), radius=d['radius_km'])}")]
    for s in stations[:5]:
        dist = f"{s['distance_km']:.1f} km" if s.get("distance_km") else ""
        kw = f"{s['max_kw']:.0f} kW" if s.get("max_kw") else ""
        addr = s.get("address") or ""
        loc_label = _maps_link(s.get("lat"), s.get("lon"), addr or (s["name"] or "EV Station"))
        name_part = escape(s["name"] or "EV Station") + (f": {loc_label}" if addr else "")
        detail = " — ".join(filter(None, [dist, kw]))
        line = f"  • {name_part}"
        if detail:
            line += f" — {detail}"
        lines.append(line)
    if len(stations) > 5:
        lines.append(f"  … and {len(stations) - 5} more")
    return "\n".join(lines)


def _format_fire(result: GeoResult, lang: str) -> str:
    if not result.ok:
        return i18n.t(lang, "geo_error", provider="forest fire", e=result.error)
    d = result.data
    fires = d.get("fires", [])
    if not fires:
        return f"🔥 {i18n.t(lang, 'geo_fire_none', radius=d['radius_km'])}"
    lines = [f"🔥 {i18n.t(lang, 'geo_fire_header', count=len(fires), radius=d['radius_km'])}"]
    for f in fires[:5]:
        lines.append(f"  ⚠️ {f['distance_km']} km — {f.get('date', '')} {f.get('time', '')} FRP:{f.get('frp', 'n/a')}")
    return "\n".join(lines)


def _format_parking(result: GeoResult, lang: str) -> str:
    if not result.ok:
        return escape(i18n.t(lang, "geo_error", provider="parking", e=result.error))
    d = result.data
    lots = d.get("lots", [])
    if not lots:
        return escape(f"🅿️ {i18n.t(lang, 'geo_parking_none')}")
    lines = [escape(f"🅿️ {i18n.t(lang, 'geo_parking_header', count=len(lots))}")]
    for lot in lots[:5]:
        name = lot.get("name") or "Parking"
        addr = lot.get("address") or ""
        dist = f"{lot['distance_km']:.2f} km" if lot.get("distance_km") is not None else ""

        # Line 1: name + map link
        loc_label = _maps_link(lot.get("lat"), lot.get("lon"), addr or name)
        name_part = escape(name) + (f": {loc_label}" if addr else f": {loc_label}")
        line = f"  • {name_part}"
        if dist:
            line += f" — {escape(dist)}"
        lines.append(line)

        # Line 2: type / access / fee / occupancy badges
        badges = []
        if lot.get("parking_type"):
            badges.append(escape(lot["parking_type"]))
        if lot.get("access"):
            badges.append(escape(lot["access"]))
        if lot.get("fee") == "yes":
            badges.append("paid")
        elif lot.get("fee") == "no":
            badges.append("free")
        if lot.get("opening_hours"):
            badges.append(escape(lot["opening_hours"]))
        if lot.get("maxheight"):
            badges.append(f"max {escape(lot['maxheight'])} m")
        if lot.get("capacity"):
            badges.append(f"cap {escape(lot['capacity'])}")
        if lot.get("free_spaces") is not None:
            free = lot["free_spaces"]
            emoji = "🟢" if free > 20 else ("🟡" if free > 5 else "🔴")
            badges.append(f"{emoji} {free} free")
        if badges:
            lines.append(f"    {' · '.join(badges)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Telegram command handlers
# ---------------------------------------------------------------------------

async def cmd_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    loc = _user_location(user)
    if user["home_lat"] is not None:
        msg = i18n.t(lang, "geo_location_set", lat=loc.lat, lon=loc.lon)
    else:
        msg = i18n.t(lang, "geo_location_default", lat=loc.lat, lon=loc.lon)
    await update.message.reply_text(msg)


async def cmd_fuel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    await update.message.reply_text(i18n.t(lang, "fetching"))
    loc = _user_location(user)
    result = await build_aggregator().get("fuel", loc)
    if not result.ok:
        await update.message.reply_text(i18n.t(lang, "fetch_error", e=result.error))
        return

    import fuel_api
    data = result.data
    summary = fuel_api.summarize(data)
    nearest = None
    if user["home_lat"] is not None and user["home_lon"] is not None:
        nearest = fuel_api.find_nearest_station(data["stations"], user["home_lat"], user["home_lon"])
    msg = fuel_api.format_message(
        summary, nearest,
        municipio_name=user["municipio_name"],
        province_code=user["province_code"],
        lang=lang,
    )
    await update.message.reply_text(msg)


async def cmd_weather_geo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    loc = _user_location(user)
    result = await build_aggregator().get("weather", loc)
    await update.message.reply_text(_format_weather(result, lang))


async def cmd_sea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    loc = _user_location(user)
    result = await build_aggregator().get("sea", loc)
    await update.message.reply_text(_format_sea(result, lang))


async def cmd_air(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    loc = _user_location(user)
    result = await build_aggregator().get("air_quality", loc)
    await update.message.reply_text(_format_air(result, lang))


async def cmd_pollen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    loc = _user_location(user)
    result = await build_aggregator().get("pollen", loc)
    await update.message.reply_text(_format_pollen(result, lang))


async def cmd_electricity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    loc = _user_location(user)
    result = await build_aggregator().get("electricity", loc)
    await update.message.reply_text(_format_electricity(result, lang))


async def cmd_ev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    loc = _user_location(user)
    result = await build_aggregator().get("ev_charging", loc)
    await update.message.reply_text(_format_ev(result, lang), parse_mode=ParseMode.HTML)


async def cmd_fire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    loc = _user_location(user)
    result = await build_aggregator().get("forest_fire", loc)
    await update.message.reply_text(_format_fire(result, lang))


async def cmd_parking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    loc = _user_location(user)
    result = await build_aggregator().get("parking", loc)
    await update.message.reply_text(_format_parking(result, lang), parse_mode=ParseMode.HTML)


async def cmd_around(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch all providers concurrently and reply with a combined summary."""
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    loc = _user_location(user)

    await update.message.reply_text(i18n.t(lang, "geo_around_fetching"))

    results = await build_aggregator().gather(loc)

    parts = []
    for name, fmt_fn in [
        ("weather", _format_weather),
        ("sea", _format_sea),
        ("air_quality", _format_air),
        ("pollen", _format_pollen),
        ("electricity", _format_electricity),
        ("forest_fire", _format_fire),
    ]:
        if name in results:
            parts.append(fmt_fn(results[name], lang))

    await update.message.reply_text("\n\n".join(parts) if parts else i18n.t(lang, "geo_no_data"))


def register_handlers(app: Application) -> None:
    """Register all geo command handlers on the given Application."""
    app.add_handler(CommandHandler("fuel", cmd_fuel))
    app.add_handler(CommandHandler("weather", cmd_weather_geo))
    app.add_handler(CommandHandler("sea", cmd_sea))
    app.add_handler(CommandHandler("air", cmd_air))
    app.add_handler(CommandHandler("pollen", cmd_pollen))
    app.add_handler(CommandHandler("electricity", cmd_electricity))
    app.add_handler(CommandHandler("ev", cmd_ev))
    app.add_handler(CommandHandler("fire", cmd_fire))
    app.add_handler(CommandHandler("parking", cmd_parking))
    app.add_handler(CommandHandler("location", cmd_location))
    app.add_handler(CommandHandler("around", cmd_around))
