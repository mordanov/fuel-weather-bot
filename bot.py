"""
Fuel price Telegram bot — interactive multi-user edition.

Commands:
  /start      — register and show help
  /check      — fetch current prices for your municipality
  /home       — set home coordinates: /home <lat> <lon>
  /municipio  — change municipality: /municipio <name>
  /predict    — predict tomorrow's prices (linear regression)
  /statistics — show price history stats
  /time       — set daily notification time: /time HH:MM
  /language   — choose language (en/es/ru)
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
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

import db
import fuel_api
import i18n
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
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    _reschedule_user(context.application, user)
    await update.message.reply_text(i18n.t(lang, "welcome"))


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    await update.message.reply_text(i18n.t(lang, "fetching"))

    try:
        data, summary = await _fetch_and_save(user["province_code"], user["municipio_name"])
    except Exception as e:
        logger.exception("fetch_and_save failed")
        await update.message.reply_text(i18n.t(lang, "fetch_error", e=e))
        return

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


async def cmd_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    args = context.args

    if len(args) != 2:
        await update.message.reply_text(i18n.t(lang, "home_usage"))
        return

    try:
        lat, lon = float(args[0]), float(args[1])
    except ValueError:
        await update.message.reply_text(i18n.t(lang, "home_invalid_numbers"))
        return

    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        await update.message.reply_text(i18n.t(lang, "home_invalid_range"))
        return

    db.update_user_home(chat_id, lat, lon)
    await update.message.reply_text(i18n.t(lang, "home_set", lat=lat, lon=lon))


async def cmd_municipio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    args = context.args

    if not args:
        await update.message.reply_text(i18n.t(lang, "municipio_usage"))
        return

    name = " ".join(args)
    province_code = user["province_code"]

    try:
        fuel_api.get_municipio_id(province_code, name)
    except ValueError:
        await update.message.reply_text(i18n.t(lang, "municipio_not_found", name=name, province=province_code))
        return

    db.update_user_municipio(chat_id, name, province_code)
    await update.message.reply_text(i18n.t(lang, "municipio_updated", name=name))


async def cmd_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    snapshots = db.get_snapshots(user["province_code"], user["municipio_name"], days=30)

    valid_g95 = [(i, s["avg_gasoline_95"]) for i, s in enumerate(snapshots) if s["avg_gasoline_95"] is not None]
    valid_diesel = [(i, s["avg_diesel"]) for i, s in enumerate(snapshots) if s["avg_diesel"] is not None]

    min_points = 3
    if len(valid_g95) < min_points or len(valid_diesel) < min_points:
        await update.message.reply_text(i18n.t(lang, "not_enough_history", n=min_points))
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
        i18n.t(lang, "predict_header", date=tomorrow.strftime("%d/%m/%Y"), scope=scope) + "\n\n"
        f"{i18n.t(lang, 'gasoline_95')}: {pred_g95:.3f} €/L\n"
        f"{i18n.t(lang, 'diesel')}:      {pred_diesel:.3f} €/L\n\n"
        + i18n.t(lang, "predict_caveat", n=len(valid_g95))
    )


async def cmd_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    snapshots = db.get_snapshots(user["province_code"], user["municipio_name"], days=60)

    if not snapshots:
        await update.message.reply_text(i18n.t(lang, "no_history"))
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
    week_ago_snap = next((s for s in snapshots if s["snapshot_date"] >= week_ago), None)

    this_month_rows = [s for s in snapshots
                       if s["snapshot_date"].month == cur_month and s["snapshot_date"].year == cur_year]
    prev_month_rows = [s for s in snapshots
                       if s["snapshot_date"].month == prev_month and s["snapshot_date"].year == prev_year]

    latest_g95 = latest["avg_gasoline_95"]
    latest_diesel = latest["avg_diesel"]
    week_g95 = week_ago_snap["avg_gasoline_95"] if week_ago_snap else None
    week_diesel = week_ago_snap["avg_diesel"] if week_ago_snap else None

    scope = user["municipio_name"] or f"province {user['province_code']}"
    lines = [i18n.t(lang, "stats_header", scope=scope), ""]

    lines.append(i18n.t(lang, "gasoline_95") + ":")
    lines.append(i18n.t(lang, "stats_latest", val=fmt(latest_g95)))
    lines.append(i18n.t(lang, "stats_week_ago", val=fmt(week_g95), trend=trend(latest_g95, week_g95)))
    lines.append(i18n.t(lang, "stats_this_month", val=fmt(avg_field(this_month_rows, "avg_gasoline_95"))))
    lines.append(i18n.t(lang, "stats_last_month", val=fmt(avg_field(prev_month_rows, "avg_gasoline_95"))))
    lines.append("")
    lines.append(i18n.t(lang, "diesel") + ":")
    lines.append(i18n.t(lang, "stats_latest", val=fmt(latest_diesel)))
    lines.append(i18n.t(lang, "stats_week_ago", val=fmt(week_diesel), trend=trend(latest_diesel, week_diesel)))
    lines.append(i18n.t(lang, "stats_this_month", val=fmt(avg_field(this_month_rows, "avg_diesel"))))
    lines.append(i18n.t(lang, "stats_last_month", val=fmt(avg_field(prev_month_rows, "avg_diesel"))))
    lines.append("")
    lines.append(i18n.t(lang, "stats_footer", n=len(snapshots)))

    await update.message.reply_text("\n".join(lines))


async def cmd_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")

    lat = user["home_lat"] if user["home_lat"] is not None else DEFAULT_LAT
    lon = user["home_lon"] if user["home_lon"] is not None else DEFAULT_LON

    try:
        weather = weather_api.fetch_weather(lat, lon)
    except Exception as e:
        logger.exception("weather fetch failed")
        await update.message.reply_text(i18n.t(lang, "weather_error", e=e))
        return

    await update.message.reply_text(weather_api.format_weather_message(weather, lat, lon, lang=lang))


async def cmd_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    args = context.args

    if not args:
        await update.message.reply_text(i18n.t(lang, "time_usage"))
        return

    try:
        h, m = args[0].split(":")
        hour, minute = int(h), int(m)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        await update.message.reply_text(i18n.t(lang, "time_invalid"))
        return

    db.update_user_send_time(chat_id, hour, minute)
    user["send_hour"] = hour
    user["send_minute"] = minute
    _reschedule_user(context.application, user)
    await update.message.reply_text(i18n.t(lang, "time_set", time=f"{hour:02d}:{minute:02d}"))


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"lang:{code}")]
        for code, name in i18n.SUPPORTED_LANGUAGES.items()
    ]
    await update.message.reply_text(
        i18n.t("en", "language_choose"),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cb_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    if lang not in i18n.SUPPORTED_LANGUAGES:
        return
    chat_id = update.effective_chat.id
    db.get_or_create_user(chat_id)
    db.update_user_language(chat_id, lang)
    await query.edit_message_text(i18n.t(lang, "language_set"))


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    db.set_notifications(chat_id, False)
    _cancel_user_job(context.application, chat_id)
    await update.message.reply_text(i18n.t(lang, "stop_done"))


# ---------------------------------------------------------------------------
# Per-user scheduled jobs
# ---------------------------------------------------------------------------

def _job_name(chat_id: int) -> str:
    return f"daily_{chat_id}"


def _cancel_user_job(app: Application, chat_id: int):
    for job in app.job_queue.get_jobs_by_name(_job_name(chat_id)):
        job.schedule_removal()


def _reschedule_user(app: Application, user: dict):
    from datetime import time as dt_time
    chat_id = user["chat_id"]
    _cancel_user_job(app, chat_id)
    if not user.get("notifications_enabled", True):
        return
    send_time = dt_time(user.get("send_hour", SEND_HOUR), user.get("send_minute", SEND_MINUTE))
    app.job_queue.run_daily(
        _user_daily_job,
        time=send_time,
        name=_job_name(chat_id),
        data=chat_id,
    )


async def _user_daily_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    user = db.get_or_create_user(chat_id)
    if not user.get("notifications_enabled", True):
        return
    lang = user.get("language", "en")

    try:
        data, summary = await _fetch_and_save(user["province_code"], user["municipio_name"])
    except Exception as e:
        logger.error("Daily fetch failed for user %s: %s", chat_id, e)
        return

    nearest = None
    if user["home_lat"] is not None and user["home_lon"] is not None:
        nearest = fuel_api.find_nearest_station(data["stations"], user["home_lat"], user["home_lon"])

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=fuel_api.format_message(
                summary, nearest,
                municipio_name=user["municipio_name"],
                province_code=user["province_code"],
                lang=lang,
            ),
        )
    except Exception as e:
        logger.error("Failed to send daily fuel message to %s: %s", chat_id, e)
        return

    lat = user["home_lat"] if user["home_lat"] is not None else DEFAULT_LAT
    lon = user["home_lon"] if user["home_lon"] is not None else DEFAULT_LON
    try:
        weather = weather_api.fetch_weather(lat, lon)
        await context.bot.send_message(
            chat_id=chat_id,
            text=weather_api.format_weather_message(weather, lat, lon, lang=lang),
        )
    except Exception as e:
        logger.error("Failed to send daily weather to %s: %s", chat_id, e)


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
    app.add_handler(CommandHandler("time", cmd_time))
    app.add_handler(CommandHandler("language", cmd_language))
    app.add_handler(CommandHandler("predict", cmd_predict))
    app.add_handler(CommandHandler("statistics", cmd_statistics))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("weather", cmd_weather))
    app.add_handler(CallbackQueryHandler(cb_language, pattern=r"^lang:"))

    # Restore per-user scheduled jobs from DB on startup
    for user in db.get_all_users():
        _reschedule_user(app, user)
    logger.info("Scheduled jobs restored for %d users", len(db.get_all_users()))

    logger.info("Bot polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
