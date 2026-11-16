from sqlalchemy import inspect, text

from . import db


def ensure_schema():
    """Bring an existing SQLite database up to date.

    `db.create_all()` creates missing tables but never adds columns to existing ones,
    so columns added after the first deployment are added here. Safe to run on every start.
    """
    columns = {column["name"] for column in inspect(db.engine).get_columns("station")}

    if "country" not in columns:
        db.session.execute(text("ALTER TABLE station ADD COLUMN country VARCHAR(100)"))

    # Everything that existed before the country column was added is a Ugandan station.
    db.session.execute(text("UPDATE station SET country = 'Uganda' WHERE country IS NULL"))
    db.session.commit()
