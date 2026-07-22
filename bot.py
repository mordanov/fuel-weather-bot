"""
Fuel price Telegram bot — interactive multi-user edition.

Commands:
  /start      — register and show help
  /check      — fetch current prices for your municipality
  /home       — set home coordinates: /home <lat> <lon>
  /municipio  — change municipality: /municipio <name>
  /predict    — predict tomorrow's prices (linear regression)
  /statistics — show price history stats
  /stop       — disable daily notifications
  /weather    — current air & sea conditions

Env vars required:
  TELEGRAM_BOT_TOKEN  — from @BotFather
  DATABASE_URL        — postgres connection string

Optional:
  PROVINCE_CODE       — INE province code, default 29 (Malaga)
  MUNICIPIO_NAME      — default municipality for new users
  SEND_HOUR           — hour for daily broadcast (default 7)
  SEND_MINUTE         — minute for daily broadcast (default 0)
"""

import logging
import os
from datetime import date, timedelta

import numpy as np
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

import db
import fuel_api
import weather_api

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
PROVINCE_CODE = os.environ.get("PROVINCE_CODE", "29")
SEND_HOUR = int(os.environ.get("SEND_HOUR", "7"))
SEND_MINUTE = int(os.environ.get("SEND_MINUTE", "0"))

# Fallback location used for weather when a user has no /home set (Malaga centre)
DEFAULT_LAT = float(os.environ.get("DEFAULT_LAT", "36.7213"))
DEFAULT_LON = float(os.environ.get("DEFAULT_LON", "-4.4214"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_snapshot_date(date_str: str) -> date:
    """Parse the API date string '22/07/2026 08:15:00' → date object."""
    return date(int(date_str[6:10]), int(date_str[3:5]), int(date_str[0:2]))


async def _fetch_and_save(province_code: str, municipio_name: str) -> dict:
    """Fetch live prices, persist snapshot, return raw data dict."""
    data = fuel_api.fetch_stations(province_code, municipio_name)
    summary = fuel_api.summarize(data)

    snapshot_date = _parse_snapshot_date(data["date"])
    db.save_snapshot(
        snapshot_date=snapshot_date,
        province_code=province_code,
        municipio_name=municipio_name,
        avg_gasoline_95=summary["fuels"]["Gasoline 95"]["avg"],
        avg_diesel=summary["fuels"]["Diesel"]["avg"],
        station_count=summary["station_count"],
        stations=data["stations"],
    )
    return data, summary


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db.get_or_create_user(chat_id)
    db.set_notifications(chat_id, True)
    await update.message.reply_text(
        "⛽ Fuel Price Bot\n\n"
        "Commands:\n"
        "  /check — current prices\n"
        "  /home <lat> <lon> — set your home location\n"
        "  /municipio <name> — change municipality\n"
        "  /predict — tomorrow's price forecast\n"
        "  /statistics — price history\n"
        "  /stop — disable daily notifications\n"
        "  /weather — current air & sea conditions"
    )


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    await update.message.reply_text("Fetching prices...")

    try:
        data, summary = await _fetch_and_save(user["province_code"], user["municipio_name"])
    except Exception as e:
        logger.exception("fetch_and_save failed")
        await update.message.reply_text(f"Error fetching prices: {e}")
        return

    nearest = None
    if user["home_lat"] is not None and user["home_lon"] is not None:
        nearest = fuel_api.find_nearest_station(data["stations"], user["home_lat"], user["home_lon"])

    msg = fuel_api.format_message(
        summary, nearest,
        municipio_name=user["municipio_name"],
        province_code=user["province_code"],
    )
    await update.message.reply_text(msg)


async def cmd_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args

    if len(args) != 2:
        await update.message.reply_text("Usage: /home <lat> <lon>\nExample: /home 36.7213 -4.4214")
        return

    try:
        lat, lon = float(args[0]), float(args[1])
    except ValueError:
        await update.message.reply_text("Both lat and lon must be numbers.")
        return

    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        await update.message.reply_text("Invalid coordinates. Lat: -90..90, Lon: -180..180.")
        return

    db.get_or_create_user(chat_id)
    db.update_user_home(chat_id, lat, lon)
    await update.message.reply_text(f"Home set to {lat}, {lon}. Use /check to see nearest station.")


async def cmd_municipio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        await update.message.reply_text("Usage: /municipio <name>\nExample: /municipio Torremolinos")
        return

    name = " ".join(args)
    user = db.get_or_create_user(chat_id)
    province_code = user["province_code"]

    try:
        fuel_api.get_municipio_id(province_code, name)
    except ValueError:
        await update.message.reply_text(
            f"Municipality '{name}' not found in province {province_code}. No changes made."
        )
        return

    db.update_user_municipio(chat_id, name, province_code)
    await update.message.reply_text(f"Municipality updated to {name}.")


async def cmd_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    snapshots = db.get_snapshots(user["province_code"], user["municipio_name"], days=30)

    valid_g95 = [(i, s["avg_gasoline_95"]) for i, s in enumerate(snapshots) if s["avg_gasoline_95"] is not None]
    valid_diesel = [(i, s["avg_diesel"]) for i, s in enumerate(snapshots) if s["avg_diesel"] is not None]

    min_points = 3
    if len(valid_g95) < min_points or len(valid_diesel) < min_points:
        await update.message.reply_text(
            f"Not enough history yet (need at least {min_points} days of data). "
            "Use /check daily to build up history."
        )
        return

    def linear_predict(pairs):
        xs = np.array([p[0] for p in pairs], dtype=float)
        ys = np.array([p[1] for p in pairs], dtype=float)
        coeffs = np.polyfit(xs, ys, 1)
        next_x = xs[-1] + 1
        return float(np.polyval(coeffs, next_x))

    pred_g95 = linear_predict(valid_g95)
    pred_diesel = linear_predict(valid_diesel)
    tomorrow = date.today() + timedelta(days=1)
    scope = user["municipio_name"] or f"province {user['province_code']}"

    await update.message.reply_text(
        f"📈 Price forecast for {tomorrow.strftime('%d/%m/%Y')} — {scope}\n\n"
        f"Gasoline 95: {pred_g95:.3f} €/L\n"
        f"Diesel:      {pred_diesel:.3f} €/L\n\n"
        f"⚠️ Based on {len(valid_g95)}-day linear trend. Fuel prices are volatile — treat as rough estimate only."
    )


async def cmd_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    snapshots = db.get_snapshots(user["province_code"], user["municipio_name"], days=60)

    if not snapshots:
        await update.message.reply_text(
            "No price history yet. Use /check to start recording data."
        )
        return

    today = date.today()
    cur_month = today.month
    cur_year = today.year
    prev_month = cur_month - 1 if cur_month > 1 else 12
    prev_year = cur_year if cur_month > 1 else cur_year - 1
    week_ago = today - timedelta(days=7)

    def avg_field(rows, field):
        vals = [r[field] for r in rows if r[field] is not None]
        return sum(vals) / len(vals) if vals else None

    def fmt(val):
        return f"{val:.3f} €/L" if val is not None else "n/a"

    def trend(latest, old):
        if latest is None or old is None:
            return ""
        diff = latest - old
        arrow = "▲" if diff > 0.001 else ("▼" if diff < -0.001 else "→")
        return f"  {arrow} {diff:+.3f}"

    latest = snapshots[-1]
    week_ago_snap = next(
        (s for s in snapshots if s["snapshot_date"] >= week_ago),
        None,
    )

    this_month_rows = [s for s in snapshots
                       if s["snapshot_date"].month == cur_month and s["snapshot_date"].year == cur_year]
    prev_month_rows = [s for s in snapshots
                       if s["snapshot_date"].month == prev_month and s["snapshot_date"].year == prev_year]

    latest_g95 = latest["avg_gasoline_95"]
    latest_diesel = latest["avg_diesel"]
    week_g95 = week_ago_snap["avg_gasoline_95"] if week_ago_snap else None
    week_diesel = week_ago_snap["avg_diesel"] if week_ago_snap else None

    scope = user["municipio_name"] or f"province {user['province_code']}"
    lines = [f"📊 Price Statistics — {scope}", ""]

    lines.append("Gasoline 95:")
    lines.append(f"  Latest:         {fmt(latest_g95)}")
    lines.append(f"  Week ago:       {fmt(week_g95)}{trend(latest_g95, week_g95)}")
    lines.append(f"  This month avg: {fmt(avg_field(this_month_rows, 'avg_gasoline_95'))}")
    lines.append(f"  Last month avg: {fmt(avg_field(prev_month_rows, 'avg_gasoline_95'))}")
    lines.append("")
    lines.append("Diesel:")
    lines.append(f"  Latest:         {fmt(latest_diesel)}")
    lines.append(f"  Week ago:       {fmt(week_diesel)}{trend(latest_diesel, week_diesel)}")
    lines.append(f"  This month avg: {fmt(avg_field(this_month_rows, 'avg_diesel'))}")
    lines.append(f"  Last month avg: {fmt(avg_field(prev_month_rows, 'avg_diesel'))}")
    lines.append("")
    lines.append(f"(Based on {len(snapshots)} days of recorded data)")

    await update.message.reply_text("\n".join(lines))


async def cmd_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)

    lat = user["home_lat"] if user["home_lat"] is not None else DEFAULT_LAT
    lon = user["home_lon"] if user["home_lon"] is not None else DEFAULT_LON

    try:
        weather = weather_api.fetch_weather(lat, lon)
    except Exception as e:
        logger.exception("weather fetch failed")
        await update.message.reply_text(f"Error fetching weather: {e}")
        return

    await update.message.reply_text(weather_api.format_weather_message(weather, lat, lon))


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db.get_or_create_user(chat_id)
    db.set_notifications(chat_id, False)
    await update.message.reply_text(
        "Daily notifications disabled. You can still use /check any time.\n"
        "Send /start to re-enable them."
    )


# ---------------------------------------------------------------------------
# Daily broadcast job
# ---------------------------------------------------------------------------

async def daily_broadcast(context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users()
    if not users:
        return

    # Group users by (province_code, municipio_name) to avoid duplicate fetches
    combos: dict[tuple, list] = {}
    for u in users:
        key = (u["province_code"], u["municipio_name"])
        combos.setdefault(key, []).append(u)

    for (province_code, municipio_name), group in combos.items():
        try:
            data, summary = await _fetch_and_save(province_code, municipio_name)
        except Exception as e:
            logger.error("Daily fetch failed for (%s, %s): %s", province_code, municipio_name, e)
            continue

        for user in group:
            nearest = None
            if user["home_lat"] is not None and user["home_lon"] is not None:
                nearest = fuel_api.find_nearest_station(
                    data["stations"], user["home_lat"], user["home_lon"]
                )

            msg = fuel_api.format_message(
                summary, nearest,
                municipio_name=municipio_name,
                province_code=province_code,
            )
            try:
                await context.bot.send_message(chat_id=user["chat_id"], text=msg)
            except Exception as e:
                logger.error("Failed to send daily fuel message to %s: %s", user["chat_id"], e)
                continue

            lat = user["home_lat"] if user["home_lat"] is not None else DEFAULT_LAT
            lon = user["home_lon"] if user["home_lon"] is not None else DEFAULT_LON
            try:
                weather = weather_api.fetch_weather(lat, lon)
                await context.bot.send_message(
                    chat_id=user["chat_id"],
                    text=weather_api.format_weather_message(weather, lat, lon),
                )
            except Exception as e:
                logger.error("Failed to send daily weather to %s: %s", user["chat_id"], e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    db.init_schema()

    app: Application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("home", cmd_home))
    app.add_handler(CommandHandler("municipio", cmd_municipio))
    app.add_handler(CommandHandler("predict", cmd_predict))
    app.add_handler(CommandHandler("statistics", cmd_statistics))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("weather", cmd_weather))

    send_time = f"{SEND_HOUR:02d}:{SEND_MINUTE:02d}"
    app.job_queue.run_daily(daily_broadcast, time=_parse_send_time(send_time))
    logger.info("Scheduled daily broadcast at %s", send_time)

    logger.info("Bot polling...")
    app.run_polling()


def _parse_send_time(time_str: str):
    from datetime import time as dt_time
    h, m = time_str.split(":")
    return dt_time(int(h), int(m))


if __name__ == "__main__":
    main()
