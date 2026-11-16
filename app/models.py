from datetime import datetime, timezone
from . import db

class Station(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    frequency = db.Column(db.String(50))
    city = db.Column(db.String(100))
    genres = db.Column(db.JSON, default=list)
    languages = db.Column(db.JSON, default=list)
    stream_url = db.Column(db.Text, nullable=True)
    stream_type = db.Column(db.String(50), nullable=True)
    bitrate = db.Column(db.Integer, nullable=True)
    website = db.Column(db.Text, nullable=True)
    logo_url = db.Column(db.Text, nullable=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    stream_reachable = db.Column(db.Boolean, nullable=True)
    last_checked = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "frequency": self.frequency,
            "city": self.city,
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
            "lastChecked": self.last_checked.isoformat() if self.last_checked else None,
        }
