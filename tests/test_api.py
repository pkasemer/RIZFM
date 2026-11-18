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


def test_requested_stations_are_present():
    app = create_app()
    client = app.test_client()
    for station_id, name in [("nrg-radio", "NRG"), ("kiis-fm", "KIIS"), ("mega-fm", "Mega FM Gulu")]:
        station = client.get(f"/api/v1/stations/{station_id}").json
        assert name in station["name"]
        assert station["streamUrl"]
        assert station["logoUrl"]


def test_seed_adds_missing_stations_without_touching_existing_ones():
    from app import db
    from app.models import Station
    from app.seed import STATIONS, seed_database

    app = create_app()
    with app.app_context():
        db.session.delete(db.session.get(Station, "cbs-fm"))
        db.session.get(Station, "nrg-radio").name = "Renamed through the API"
        db.session.commit()

        seed_database()

        assert db.session.query(Station).count() == len(STATIONS)
        assert db.session.get(Station, "cbs-fm") is not None
        assert db.session.get(Station, "nrg-radio").name == "Renamed through the API"


def test_station_ids_are_unique():
    from app.seed import STATIONS

    ids = [s["id"] for s in STATIONS]
    assert len(ids) == len(set(ids))


def test_stations():
    app = create_app()
    client = app.test_client()
    response = client.get("/api/v1/stations")
    assert response.status_code == 200
    assert "data" in response.json
    assert len(response.json["data"]) > 0


def test_privacy_and_delete_data_pages_are_public():
    app = create_app()
    client = app.test_client()
    for path, heading in [
        ("/privacy", "Privacy Policy"),
        ("/privacy-policy", "Privacy Policy"),
        ("/delete-data", "Delete your data"),
        ("/data-deletion", "Delete your data"),
    ]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.mimetype == "text/html"
        assert heading in response.get_data(as_text=True)


def test_legal_pages_show_contact_email_only_when_configured():
    app = create_app()
    app.config["PRIVACY_CONTACT_EMAIL"] = ""
    client = app.test_client()
    html = client.get("/privacy").get_data(as_text=True)
    assert "mailto:" not in html
    assert "support contact listed" in html

    app.config["PRIVACY_CONTACT_EMAIL"] = "privacy@example.com"
    for path in ("/privacy", "/delete-data"):
        assert "mailto:privacy@example.com" in client.get(path).get_data(as_text=True)


def test_home_page_links_to_legal_pages():
    html = create_app().test_client().get("/").get_data(as_text=True)
    assert 'href="/privacy"' in html
    assert 'href="/delete-data"' in html


def test_landing_page_is_a_personal_take_on_designing_the_app():
    app = create_app()
    app.config["APP_VERSION"] = "2.3.4"
    html = app.test_client().get("/").get_data(as_text=True)

    # The app is called RIZFM, not the old name.
    assert "RIZFM" in html and "SOFIZ" not in html
    assert "A personal take on online radio" in html
    for idea in ["Radio should just start", "Controls should feel like a radio", "The station is the star",
                 "Nobody should have to touch the volume", "Quiet, and minding its own business",
                 "Calm, minimal, a little Japanese"]:
        assert idea in html, idea
    assert "What I left out" in html and "Small things I cared about" in html

    # Versions and the API are still on the page, under "Under the hood".
    assert "2.3.4" in html and "/api/v1/stations" in html and 'id="build"' in html
    # Things the app does not do must not be advertised as features.
    assert "No downloads" in html and "Not the current song" in html


def test_the_app_name_can_still_be_configured(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Another FM")
    html = create_app().test_client().get("/").get_data(as_text=True)
    assert "Another FM" in html and "RIZFM" not in html.split("<main>")[1].split("</main>")[0]


def test_all_pages_share_the_site_layout():
    client = create_app().test_client()
    for path in ("/", "/privacy", "/delete-data"):
        html = client.get(path).get_data(as_text=True)
        assert 'class="brand-mark"' in html, path
        assert 'href="/privacy"' in html and 'href="/delete-data"' in html, path
        assert "<style>" in html and "--accent" in html, path


def test_legal_pages_cover_the_image_cache():
    client = create_app().test_client()
    assert "Clear image cache" in client.get("/privacy").get_data(as_text=True)
    assert "Clear image cache" in client.get("/delete-data").get_data(as_text=True)


def test_international_stations_have_a_country_and_can_be_filtered():
    client = create_app().test_client()

    heart = client.get("/api/v1/stations/heart-uk").json
    assert heart["country"] == "United Kingdom"
    assert heart["streamUrl"] and heart["logoUrl"]

    klove = client.get("/api/v1/stations/k-love").json
    assert klove["country"] == "United States"

    # Everything that is not explicitly international is Ugandan.
    assert client.get("/api/v1/stations/capital-fm").json["country"] == "Uganda"

    uk = client.get("/api/v1/stations?country=united kingdom").json["data"]
    assert [s["id"] for s in uk] == ["heart-uk"]
    from app.seed import STATIONS

    international = [s for s in STATIONS if s.get("country", "Uganda") != "Uganda"]
    ug = client.get("/api/v1/stations?country=Uganda&limit=1").json
    everything = client.get("/api/v1/stations?limit=1").json
    assert ug["pagination"]["total"] == everything["pagination"]["total"] - len(international)


def test_station_country_can_be_set_through_the_api():
    client = create_app().test_client()
    created = client.post("/api/v1/stations", json={"id": "x-fm", "name": "X FM", "country": "Kenya"})
    assert created.status_code == 201 and created.json["country"] == "Kenya"
    assert client.post("/api/v1/stations", json={"id": "y-fm", "name": "Y FM"}).json["country"] == "Uganda"
    assert client.put("/api/v1/stations/x-fm", json={"country": "Tanzania"}).json["country"] == "Tanzania"


def test_existing_database_without_country_column_is_upgraded(tmp_path, monkeypatch):
    import sqlite3

    db_file = tmp_path / "old.db"
    conn = sqlite3.connect(db_file)
    # The schema as it was before the country column existed, with one user-edited station.
    conn.execute(
        "CREATE TABLE station (id VARCHAR(100) PRIMARY KEY, name VARCHAR(200) NOT NULL, frequency VARCHAR(50), "
        "city VARCHAR(100), genres JSON, languages JSON, stream_url TEXT, stream_type VARCHAR(50), bitrate INTEGER, "
        "website TEXT, logo_url TEXT, is_featured BOOLEAN, is_active BOOLEAN, stream_reachable BOOLEAN, "
        "last_checked DATETIME, created_at DATETIME, updated_at DATETIME)"
    )
    conn.execute("INSERT INTO station (id, name, is_active) VALUES ('capital-fm', 'My renamed Capital', 1)")
    conn.commit()
    conn.close()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    client = create_app().test_client()

    capital = client.get("/api/v1/stations/capital-fm").json
    assert capital["name"] == "My renamed Capital"  # existing edits are kept
    assert capital["country"] == "Uganda"  # old rows are backfilled
    assert client.get("/api/v1/stations/heart-uk").json["country"] == "United Kingdom"  # new stations arrive


def test_us_hip_hop_and_tennessee_country_stations():
    client = create_app().test_client()
    us = {s["id"]: s for s in client.get("/api/v1/stations?country=United States&limit=100").json["data"]}

    hip_hop = {"hot-97", "power-105", "power-106", "real-923", "wjlb"}
    tennessee_country = {"wsm-650", "big-98", "wcyq-wolf", "kix-106"}
    assert hip_hop | tennessee_country | {"k-love"} == set(us)

    for station_id in hip_hop:
        assert "Hip-Hop" in us[station_id]["genres"], station_id
    for station_id in tennessee_country:
        assert "Country" in us[station_id]["genres"], station_id
    for station in us.values():
        assert station["streamUrl"] and station["logoUrl"], station["id"]

    # The genre filter finds them too.
    country = client.get("/api/v1/stations?genre=Country&limit=100").json["data"]
    assert tennessee_country <= {s["id"] for s in country}


def test_genre_filter_matches_any_genre_of_a_station_not_only_a_sole_genre():
    client = create_app().test_client()

    def ids(genre):
        data = client.get("/api/v1/stations", query_string={"genre": genre, "limit": 100}).json["data"]
        return {s["id"] for s in data}

    # capital-fm is ["Pop", "Adult Contemporary", "Talk"]; wsm-650 is ["Country", "Classic Country"].
    assert "capital-fm" in ids("Pop") and "capital-fm" in ids("Talk") and "capital-fm" in ids("Adult Contemporary")
    assert "wsm-650" in ids("Country") and "wsm-650" in ids("Classic Country")
    assert "capital-fm" in ids("pop")  # case-insensitive
    assert ids("Count") == set()       # a part of a genre name is not a match
    assert ids("Polka") == set()
    assert ids("Music") > {"beat-fm", "galaxy-fm"}  # many stations list Music among several genres


def test_o_radio_is_live_with_a_stream_that_does_not_depend_on_an_expiring_token():
    client = create_app().test_client()

    station = client.get("/api/v1/stations/o-radio").json
    assert station["name"] == "O Radio" and station["city"] == "Lira" and station["country"] == "Uganda"
    assert station["languages"] == ["Luo"]
    assert station["frequency"] is None  # internet-only: no FM frequency
    assert station["logoUrl"].endswith("/static/logos/o-radio.png")
    assert client.get("/static/logos/o-radio.png").status_code == 200

    # The link the station gives out has "?rj-ttl=5&rj-tok=..."; that token expires, so it must not be stored.
    assert station["streamUrl"] == "https://stream.radiojar.com/xwy6byka3f3vv"
    assert station["streamType"] == "mp3" and station["bitrate"] == 128

    assert station["isActive"] is True
    active = {s["id"] for s in client.get("/api/v1/stations?active=true&limit=100").json["data"]}
    assert "o-radio" in active
    assert [s["id"] for s in client.get("/api/v1/stations?city=Lira").json["data"]] == ["o-radio"]


def test_no_seeded_stream_url_carries_an_expiring_token():
    from app.seed import STATIONS

    # Zeno (zt=) and Radiojar (rj-tok=) links copied from a player stop working after a short time.
    for item in STATIONS:
        url = item.get("streamUrl") or ""
        assert "zt=" not in url and "rj-tok" not in url and "rj-ttl" not in url, item["id"]
