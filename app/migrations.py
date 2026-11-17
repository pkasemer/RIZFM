from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from . import db


def _add_column(existing, name, ddl):
    """ALTER TABLE ... ADD COLUMN, tolerating a second process that added it first."""
    if name in existing:
        return
    try:
        db.session.execute(text(f"ALTER TABLE station ADD COLUMN {ddl}"))
        db.session.commit()
    except OperationalError as exc:
        db.session.rollback()
        if "duplicate column" not in str(exc).lower():
            raise


def ensure_schema():
    """Bring an existing SQLite database up to date.

    `db.create_all()` creates missing tables but never adds columns to existing ones,
    so columns added after the first deployment are added here. Safe to run on every start,
    and safe if the API and the loudness worker start at the same moment.
    """
    columns = {column["name"] for column in inspect(db.engine).get_columns("station")}

    _add_column(columns, "country", "country VARCHAR(100)")
    _add_column(columns, "loudness_lufs", "loudness_lufs FLOAT")
    _add_column(columns, "loudness_measured_at", "loudness_measured_at DATETIME")
    # Existing stations have never been measured, so they start out pending.
    _add_column(columns, "loudness_pending", "loudness_pending BOOLEAN NOT NULL DEFAULT 1")
    _add_column(columns, "loudness_fail_streak", "loudness_fail_streak INTEGER NOT NULL DEFAULT 0")

    # Stream health. Existing stations have never been checked, so they stay 'unknown' with no
    # next-check time, which the health worker reads as "check now".
    _add_column(columns, "stream_status", "stream_status VARCHAR(20) NOT NULL DEFAULT 'unknown'")
    _add_column(columns, "last_online_at", "last_online_at DATETIME")
    _add_column(columns, "response_time_ms", "response_time_ms INTEGER")
    _add_column(columns, "stream_failures", "stream_failures INTEGER NOT NULL DEFAULT 0")
    _add_column(columns, "last_error", "last_error VARCHAR(50)")
    _add_column(columns, "stream_silent", "stream_silent BOOLEAN NOT NULL DEFAULT 0")
    _add_column(columns, "health_next_check_at", "health_next_check_at DATETIME")
    _add_column(columns, "offline_since", "offline_since DATETIME")
    _add_column(columns, "offline_reminded_at", "offline_reminded_at DATETIME")

    # Everything that existed before the country column was added is a Ugandan station.
    db.session.execute(text("UPDATE station SET country = 'Uganda' WHERE country IS NULL"))
    db.session.commit()
