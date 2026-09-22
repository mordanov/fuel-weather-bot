"""
Earthquake command handler and broadcast job.
"""

import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes

import db
import i18n
import terremoto

logger = logging.getLogger(__name__)


def seed_earthquake_cache_if_empty():
    """On first deploy (empty DB table), pre-mark last 2 days as seen so we don't flood users."""
    if not db.is_earthquake_cache_empty():
        return
    disk_ids = db._load_disk_earthquake_cache()
    if disk_ids:
        db.mark_earthquakes_seen(list(disk_ids))
        logger.info("Earthquake cache seeded from disk (%d events)", len(disk_ids))
        return
    try:
        starttime = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
        recent = terremoto.fetch_recent_quakes(starttime=starttime)
        ids = [q["id"] for q in recent]
        db.mark_earthquakes_seen(ids)
        logger.info("Earthquake cache pre-seeded with %d events (no alerts sent)", len(ids))
    except Exception as e:
        logger.error("Failed to seed earthquake cache: %s", e)


async def cmd_earthquake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    tz_offset = user.get("timezone_offset", 0)

    await update.message.reply_text(i18n.t(lang, "earthquake_fetching"))

    try:
        quakes = terremoto.fetch_recent_quakes()
    except Exception as e:
        logger.exception("Earthquake fetch failed")
        await update.message.reply_text(i18n.t(lang, "fetch_error", e=e))
        return

    if not quakes:
        await update.message.reply_text(i18n.t(lang, "earthquake_none"))
        return

    for feature in quakes[:3]:
        lon, lat, _ = feature["geometry"]["coordinates"]
        nearest = terremoto.reverse_geocode(lat, lon)
        msg = terremoto.format_message(feature, nearest_place=nearest, lang=lang, tz_offset=tz_offset)
        await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)


async def earthquake_check_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        quakes = terremoto.fetch_recent_quakes()
    except Exception as e:
        logger.error("Earthquake fetch failed: %s", e)
        return

    seen = db.get_seen_earthquake_ids()
    new_quakes = [q for q in quakes if q["id"] not in seen]
    new_quakes.reverse()

    if not new_quakes:
        return

    users = db.get_all_users()
    newly_seen = []
    for q in new_quakes:
        lon, lat, _ = q["geometry"]["coordinates"]
        nearest = terremoto.reverse_geocode(lat, lon)
        sent = False
        for user in users:
            lang = user.get("language", "en")
            tz_offset = user.get("timezone_offset", 0)
            msg = terremoto.format_message(q, nearest_place=nearest, lang=lang, tz_offset=tz_offset)
            try:
                await context.bot.send_message(
                    chat_id=user["chat_id"],
                    text=msg,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                sent = True
            except Exception as e:
                logger.error("Failed to send earthquake alert to %s: %s", user["chat_id"], e)
        if sent:
            newly_seen.append(q["id"])
            logger.info("Earthquake alerted: %s", q["id"])

    db.mark_earthquakes_seen(newly_seen)
