"""
Fuel price Telegram bot — interactive multi-user edition.

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

from telegram import BotCommand
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler

import db
from handlers.earthquake import cmd_earthquake, earthquake_check_job, seed_earthquake_cache_if_empty
from handlers.fuel_commands import cmd_check, cmd_municipio, cmd_predict, cmd_province, cmd_statistics
from handlers.scheduling import reschedule_user
from handlers.user_settings import (
    cb_language, cmd_home, cmd_language, cmd_start, cmd_stop, cmd_time, cmd_timezone,
)
from geo.commands import register_handlers as register_geo_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

import terremoto

_BOT_COMMANDS = [
    BotCommand("check",       "Current fuel prices"),
    BotCommand("weather",     "Air conditions"),
    BotCommand("sea",         "Sea temperature & waves"),
    BotCommand("air",         "Air quality index"),
    BotCommand("pollen",      "Pollen levels"),
    BotCommand("electricity", "Electricity spot price"),
    BotCommand("ev",          "EV charging stations nearby"),
    BotCommand("earthquake",  "Latest earthquakes in the region"),
    BotCommand("fire",        "Active forest fires nearby"),
    BotCommand("parking",     "Parking lots nearby"),
    BotCommand("around",      "Combined geo snapshot"),
    BotCommand("predict",     "Tomorrow's price forecast"),
    BotCommand("statistics",  "Price history"),
    BotCommand("home",        "Set home location: /home <lat> <lon>"),
    BotCommand("province",    "Change province: /province <name>"),
    BotCommand("municipio",   "Change municipality"),
    BotCommand("time",        "Daily notification time: /time HH:MM"),
    BotCommand("timezone",    "Set timezone offset: /timezone +2"),
    BotCommand("language",    "Change language"),
    BotCommand("location",    "Show current location"),
    BotCommand("stop",        "Disable daily notifications"),
    BotCommand("start",       "Show help"),
]


async def _post_init(app: Application) -> None:
    await app.bot.set_my_commands(_BOT_COMMANDS)
    logger.info("Bot commands registered (%d)", len(_BOT_COMMANDS))


def main():
    db.init_schema()
    seed_earthquake_cache_if_empty()

    app: Application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("home", cmd_home))
    app.add_handler(CommandHandler("province", cmd_province))
    app.add_handler(CommandHandler("municipio", cmd_municipio))
    app.add_handler(CommandHandler("time", cmd_time))
    app.add_handler(CommandHandler("language", cmd_language))
    app.add_handler(CommandHandler("predict", cmd_predict))
    app.add_handler(CommandHandler("statistics", cmd_statistics))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("earthquake", cmd_earthquake))
    app.add_handler(CommandHandler("timezone", cmd_timezone))
    app.add_handler(CallbackQueryHandler(cb_language, pattern=r"^lang:"))

    register_geo_handlers(app)

    for user in db.get_all_users():
        reschedule_user(app, user)
    logger.info("Scheduled jobs restored for %d users", len(db.get_all_users()))

    app.job_queue.run_repeating(
        earthquake_check_job,
        interval=terremoto.POLL_SECONDS,
        first=10,
        name="earthquake_check",
    )
    logger.info("Earthquake check job scheduled every %ds", terremoto.POLL_SECONDS)

    logger.info("Bot polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
