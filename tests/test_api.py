import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app import create_app

def test_health():
    app = create_app()
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"

def test_every_station_has_a_square_logo():
    from pathlib import Path
    from app.seed import STATIONS

    app = create_app()
    client = app.test_client()
    stations = client.get("/api/v1/stations?limit=100").json["data"]
    assert len(stations) == len(STATIONS)
    for station in stations:
        assert station["logoUrl"].endswith(f"/static/logos/{station['id']}.png")
        response = client.get(f"/static/logos/{station['id']}.png")
        assert response.status_code == 200
        assert response.mimetype == "image/png"
        # PNG IHDR: width and height are big-endian ints at bytes 16-24
        data = response.data
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        assert width == height, station["id"]


def test_backfill_keeps_custom_logos():
    from app import db
    from app.models import Station
    from app.seed import backfill_logos

    app = create_app()
    with app.app_context():
        db.session.get(Station, "kfm").logo_url = None
        db.session.get(Station, "xfm").logo_url = "https://example.com/custom.png"
        db.session.commit()
        backfill_logos()
        assert db.session.get(Station, "kfm").logo_url.endswith("/static/logos/kfm.png")
        assert db.session.get(Station, "xfm").logo_url == "https://example.com/custom.png"


def test_stations():
    app = create_app()
    client = app.test_client()
    response = client.get("/api/v1/stations")
    assert response.status_code == 200
    assert "data" in response.json
    assert len(response.json["data"]) > 0
