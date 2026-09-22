"""
Per-user daily job scheduling (fuel prices + weather).
"""

import logging
import os

from telegram.ext import Application, ContextTypes

import db
import fuel_api
import weather_api

logger = logging.getLogger(__name__)

SEND_HOUR = int(os.environ.get("SEND_HOUR", "7"))
SEND_MINUTE = int(os.environ.get("SEND_MINUTE", "0"))
DEFAULT_LAT = float(os.environ.get("DEFAULT_LAT", "36.7213"))
DEFAULT_LON = float(os.environ.get("DEFAULT_LON", "-4.4214"))


def job_name(chat_id: int) -> str:
    return f"daily_{chat_id}"


def cancel_user_job(app: Application, chat_id: int):
    for job in app.job_queue.get_jobs_by_name(job_name(chat_id)):
        job.schedule_removal()


def reschedule_user(app: Application, user: dict):
    from datetime import time as dt_time
    chat_id = user["chat_id"]
    cancel_user_job(app, chat_id)
    if not user.get("notifications_enabled", True):
        return
    send_time = dt_time(user.get("send_hour", SEND_HOUR), user.get("send_minute", SEND_MINUTE))
    app.job_queue.run_daily(
        _user_daily_job,
        time=send_time,
        name=job_name(chat_id),
        data=chat_id,
    )


async def _user_daily_job(context: ContextTypes.DEFAULT_TYPE):
    from handlers.fuel_commands import fetch_and_save
    import i18n

    chat_id = context.job.data
    user = db.get_or_create_user(chat_id)
    if not user.get("notifications_enabled", True):
        return
    lang = user.get("language", "en")

    try:
        data, summary = await fetch_and_save(user["province_code"], user["municipio_name"])
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
