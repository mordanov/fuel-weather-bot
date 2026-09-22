"""
Telegram command handlers for user settings (home, time, language, timezone, stop).
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import db
import i18n
from handlers.scheduling import reschedule_user

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db.get_or_create_user(chat_id)
    db.set_notifications(chat_id, True)
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    reschedule_user(context.application, user)
    await update.message.reply_text(i18n.t(lang, "welcome"))


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
    reschedule_user(context.application, user)
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
    from handlers.scheduling import cancel_user_job
    cancel_user_job(context.application, chat_id)
    await update.message.reply_text(i18n.t(lang, "stop_done"))


async def cmd_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")

    if not context.args:
        await update.message.reply_text(i18n.t(lang, "timezone_usage"))
        return

    try:
        offset = int(context.args[0])
        if not (-12 <= offset <= 14):
            raise ValueError
    except (ValueError, IndexError):
        await update.message.reply_text(i18n.t(lang, "timezone_invalid"))
        return

    db.update_user_timezone(chat_id, offset)
    tz_label = "UTC" if offset == 0 else f"UTC{offset:+d}"
    await update.message.reply_text(i18n.t(lang, "timezone_set", offset=tz_label))
