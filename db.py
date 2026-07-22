"""
PostgreSQL persistence for fuel price history and per-user settings.
"""

import json
import os

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_DEFAULT_PROVINCE = os.environ.get("PROVINCE_CODE", "29")
_DEFAULT_MUNICIPIO = os.environ.get("MUNICIPIO_NAME", "")


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_schema():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    chat_id               BIGINT PRIMARY KEY,
                    home_lat              FLOAT,
                    home_lon              FLOAT,
                    municipio_name        TEXT NOT NULL DEFAULT '',
                    province_code         TEXT NOT NULL DEFAULT '29',
                    notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    send_hour             INT NOT NULL DEFAULT 7,
                    send_minute           INT NOT NULL DEFAULT 0,
                    language              TEXT NOT NULL DEFAULT 'en',
                    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE
            """)
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS send_hour INT NOT NULL DEFAULT 7
            """)
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS send_minute INT NOT NULL DEFAULT 0
            """)
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT 'en'
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS price_snapshots (
                    id              SERIAL PRIMARY KEY,
                    snapshot_date   DATE NOT NULL,
                    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    province_code   TEXT NOT NULL,
                    municipio_name  TEXT NOT NULL DEFAULT '',
                    avg_gasoline_95 FLOAT,
                    avg_diesel      FLOAT,
                    station_count   INTEGER,
                    stations_json   JSONB,
                    UNIQUE(snapshot_date, province_code, municipio_name)
                )
            """)
        conn.commit()


def get_or_create_user(chat_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO users (chat_id, municipio_name, province_code)
                VALUES (%s, %s, %s)
                ON CONFLICT (chat_id) DO NOTHING
            """, (chat_id, _DEFAULT_MUNICIPIO, _DEFAULT_PROVINCE))
            conn.commit()
            cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
            return dict(cur.fetchone())


def update_user_home(chat_id: int, lat: float, lon: float):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET home_lat = %s, home_lon = %s, updated_at = NOW()
                WHERE chat_id = %s
            """, (lat, lon, chat_id))
        conn.commit()


def update_user_municipio(chat_id: int, municipio_name: str, province_code: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users
                SET municipio_name = %s, province_code = %s, updated_at = NOW()
                WHERE chat_id = %s
            """, (municipio_name, province_code, chat_id))
        conn.commit()


def save_snapshot(
    snapshot_date,
    province_code: str,
    municipio_name: str,
    avg_gasoline_95,
    avg_diesel,
    station_count: int,
    stations: list,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO price_snapshots
                    (snapshot_date, province_code, municipio_name,
                     avg_gasoline_95, avg_diesel, station_count, stations_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (snapshot_date, province_code, municipio_name) DO NOTHING
            """, (
                snapshot_date, province_code, municipio_name,
                avg_gasoline_95, avg_diesel, station_count,
                json.dumps(stations),
            ))
        conn.commit()


def get_snapshots(province_code: str, municipio_name: str, days: int = 30) -> list:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT snapshot_date, avg_gasoline_95, avg_diesel, station_count
                FROM price_snapshots
                WHERE province_code = %s AND municipio_name = %s
                  AND snapshot_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
                ORDER BY snapshot_date ASC
            """, (province_code, municipio_name, days))
            return [dict(r) for r in cur.fetchall()]


def get_snapshot_on_date(province_code: str, municipio_name: str, date) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM price_snapshots
                WHERE province_code = %s AND municipio_name = %s
                  AND snapshot_date = %s
            """, (province_code, municipio_name, date))
            row = cur.fetchone()
            return dict(row) if row else None


def update_user_send_time(chat_id: int, hour: int, minute: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET send_hour = %s, send_minute = %s, updated_at = NOW()
                WHERE chat_id = %s
            """, (hour, minute, chat_id))
        conn.commit()


def update_user_language(chat_id: int, language: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET language = %s, updated_at = NOW()
                WHERE chat_id = %s
            """, (language, chat_id))
        conn.commit()


def set_notifications(chat_id: int, enabled: bool):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET notifications_enabled = %s, updated_at = NOW()
                WHERE chat_id = %s
            """, (enabled, chat_id))
        conn.commit()


def get_all_users() -> list:
    """Return users who have daily notifications enabled."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE notifications_enabled = TRUE")
            return [dict(r) for r in cur.fetchall()]
