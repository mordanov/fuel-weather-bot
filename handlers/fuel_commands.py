"""
Telegram command handlers for fuel prices, predictions and statistics.
"""

import logging
from datetime import date, timedelta
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from telegram import Update
from telegram.ext import ContextTypes

import db
import fuel_api
import i18n

logger = logging.getLogger(__name__)


def _parse_snapshot_date(date_str: str) -> date:
    """Parse the API date string '22/07/2026 08:15:00' → date object."""
    return date(int(date_str[6:10]), int(date_str[3:5]), int(date_str[0:2]))


async def fetch_and_save(province_code: str, municipio_name: str) -> tuple:
    """Fetch live prices, persist snapshot, return (data, summary)."""
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


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    await update.message.reply_text(i18n.t(lang, "fetching"))

    try:
        data, summary = await fetch_and_save(user["province_code"], user["municipio_name"])
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


async def cmd_province(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_or_create_user(chat_id)
    lang = user.get("language", "en")
    args = context.args

    if not args:
        await update.message.reply_text(i18n.t(lang, "province_usage"))
        return

    name = " ".join(args)
    try:
        code = fuel_api.find_province_code(name)
    except ValueError:
        await update.message.reply_text(i18n.t(lang, "province_not_found", name=name))
        return

    db.update_user_municipio(chat_id, "", code)
    await update.message.reply_text(i18n.t(lang, "province_updated", name=name, code=code))


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

    pred_g95 = fuel_api.predict_next_price(valid_g95)
    pred_diesel = fuel_api.predict_next_price(valid_diesel)
    tomorrow = date.today() + timedelta(days=1)
    scope = user["municipio_name"] or f"province {user['province_code']}"

    await update.message.reply_text(
        i18n.t(lang, "predict_header", date=tomorrow.strftime("%d/%m/%Y"), scope=scope) + "\n\n"
        f"{i18n.t(lang, 'gasoline_95')}: {pred_g95:.3f} €/L\n"
        f"{i18n.t(lang, 'diesel')}:      {pred_diesel:.3f} €/L\n\n"
        + i18n.t(lang, "predict_caveat", n=len(valid_g95))
    )


_C_G95 = "#2a78d6"     # blue   — Gasoline 95
_C_DIESEL = "#eb6834"  # orange — Diesel


def _price_chart(snapshots: list, scope: str) -> BytesIO | None:
    """Return a PNG BytesIO with price history + linear trend, or None if < 2 data points."""
    pts_g95 = [(s["snapshot_date"], s["avg_gasoline_95"]) for s in snapshots if s["avg_gasoline_95"] is not None]
    pts_diesel = [(s["snapshot_date"], s["avg_diesel"]) for s in snapshots if s["avg_diesel"] is not None]

    if len(pts_g95) < 2 and len(pts_diesel) < 2:
        return None

    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8F9FA")

    def _plot(pts, color, label):
        if len(pts) < 2:
            return
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, color=color, linewidth=2, label=label, solid_capstyle="round", zorder=3)
        xi = np.arange(len(xs), dtype=float)
        trend_ys = np.polyval(np.polyfit(xi, ys, 1), xi)
        ax.plot(xs, trend_ys, color=color, linewidth=1.5, linestyle="--", alpha=0.5, zorder=2)

    _plot(pts_g95, _C_G95, "Gasoline 95")
    _plot(pts_diesel, _C_DIESEL, "Diesel")

    # X-axis: weekly ticks if >3 weeks, else every 5 days
    all_dates = [p[0] for p in pts_g95 + pts_diesel]
    span_days = (max(all_dates) - min(all_dates)).days if all_dates else 0
    if span_days > 21:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
    else:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    fig.autofmt_xdate(rotation=30, ha="right")

    ax.set_ylabel("€/L", fontsize=10, color="#374151")
    n = len(snapshots)
    ax.set_title(f"Fuel prices — {scope}  ({n} days)", fontsize=11, color="#111827", pad=8)
    ax.legend(loc="best", fontsize=9, framealpha=0.85, edgecolor="#D1D5DB")
    # Recessive hairline horizontal grid only
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#D1D5DB")
    ax.spines["bottom"].set_color("#D1D5DB")
    ax.tick_params(colors="#6B7280", labelsize=8)
    # Small annotation marking the dashed lines as trend
    ax.annotate("— — trend", xy=(0.99, 0.02), xycoords="axes fraction",
                ha="right", va="bottom", fontsize=7.5, color="#9CA3AF", style="italic")

    plt.tight_layout(pad=1.2)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


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

    def price_trend(latest, old):
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
    lines.append(i18n.t(lang, "stats_week_ago", val=fmt(week_g95), trend=price_trend(latest_g95, week_g95)))
    lines.append(i18n.t(lang, "stats_this_month", val=fmt(avg_field(this_month_rows, "avg_gasoline_95"))))
    lines.append(i18n.t(lang, "stats_last_month", val=fmt(avg_field(prev_month_rows, "avg_gasoline_95"))))
    lines.append("")
    lines.append(i18n.t(lang, "diesel") + ":")
    lines.append(i18n.t(lang, "stats_latest", val=fmt(latest_diesel)))
    lines.append(i18n.t(lang, "stats_week_ago", val=fmt(week_diesel), trend=price_trend(latest_diesel, week_diesel)))
    lines.append(i18n.t(lang, "stats_this_month", val=fmt(avg_field(this_month_rows, "avg_diesel"))))
    lines.append(i18n.t(lang, "stats_last_month", val=fmt(avg_field(prev_month_rows, "avg_diesel"))))
    lines.append("")
    lines.append(i18n.t(lang, "stats_footer", n=len(snapshots)))

    stats_text = "\n".join(lines)
    chart = _price_chart(snapshots, scope)

    if chart:
        caption = stats_text if len(stats_text) <= 1024 else None
        await update.message.reply_photo(photo=chart, caption=caption)
        if caption is None:
            await update.message.reply_text(stats_text)
    else:
        await update.message.reply_text(stats_text)
