from datetime import datetime, timezone
from . import db


def iso_utc(value):
    """ISO 8601 with an explicit UTC offset.

    SQLite hands datetimes back without a timezone even though they were stored as UTC,
    so a naive value is treated as UTC.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class Station(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    frequency = db.Column(db.String(50))
    city = db.Column(db.String(100))
    country = db.Column(db.String(100), default="Uganda")
    genres = db.Column(db.JSON, default=list)
    languages = db.Column(db.JSON, default=list)
    stream_url = db.Column(db.Text, nullable=True)
    stream_type = db.Column(db.String(50), nullable=True)
    bitrate = db.Column(db.Integer, nullable=True)
    website = db.Column(db.Text, nullable=True)
    logo_url = db.Column(db.Text, nullable=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    # Stream health, filled in by the health worker (app/health_worker.py).
    # `stream_reachable` and `last_checked` are the original fields; `stream_reachable` is always
    # derived from `stream_status` (online/degraded -> True, offline -> False, unknown -> None).
    stream_reachable = db.Column(db.Boolean, nullable=True)
    last_checked = db.Column(db.DateTime(timezone=True), nullable=True)
    stream_status = db.Column(db.String(20), nullable=False, default="unknown", server_default=db.text("'unknown'"))
    last_online_at = db.Column(db.DateTime(timezone=True), nullable=True)
    response_time_ms = db.Column(db.Integer, nullable=True)
    # Internal, not part of the public station response:
    stream_failures = db.Column(db.Integer, nullable=False, default=0, server_default=db.text("0"))
    last_error = db.Column(db.String(50), nullable=True)
    stream_silent = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("0"))
    health_next_check_at = db.Column(db.DateTime(timezone=True), nullable=True)  # None = check as soon as possible
    offline_since = db.Column(db.DateTime(timezone=True), nullable=True)
    offline_reminded_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Loudness (LUFS), measured by the loudness worker. See app/services/loudness.py.
    loudness_lufs = db.Column(db.Float, nullable=True)
    loudness_measured_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # True = measure on the worker's next pass (new station, changed stream URL, never measured).
    loudness_pending = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("1"))
    # Failed runs in a row since the last accepted measurement. Not part of the API.
    loudness_fail_streak = db.Column(db.Integer, nullable=False, default=0, server_default=db.text("0"))

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "frequency": self.frequency,
            "city": self.city,
            "country": self.country or "Uganda",
            "genres": self.genres or [],
            "languages": self.languages or [],
            "streamUrl": self.stream_url,
            "streamType": self.stream_type,
            "bitrate": self.bitrate,
            "website": self.website,
            "logoUrl": self.logo_url,
            "isFeatured": self.is_featured,
            "isActive": self.is_active,
            "streamReachable": self.stream_reachable,
            "lastChecked": iso_utc(self.last_checked),
            "streamStatus": self.stream_status or "unknown",
            "lastOnlineAt": iso_utc(self.last_online_at),
            "responseTimeMs": self.response_time_ms,
            "loudnessLufs": self.loudness_lufs,
            "loudnessMeasuredAt": iso_utc(self.loudness_measured_at),
        }


class LoudnessMeasurement(db.Model):
    """One accepted loudness reading. Kept so odd station values can be traced back."""

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    station_id = db.Column(db.String(100), db.ForeignKey("station.id"), nullable=False, index=True)
    lufs = db.Column(db.Float, nullable=False)
    measured_at = db.Column(db.DateTime(timezone=True), nullable=False,
                            default=lambda: datetime.now(timezone.utc), index=True)


class StreamCheck(db.Model):
    """One health probe (pass or fail). Debugging data, and the source of the uptime percentage."""

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    station_id = db.Column(db.String(100), db.ForeignKey("station.id"), nullable=False, index=True)
    checked_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc), index=True)
    ok = db.Column(db.Boolean, nullable=False)
    error = db.Column(db.String(50), nullable=True)
    response_ms = db.Column(db.Integer, nullable=True)
