from flask import Blueprint, request
from sqlalchemy import or_, text
from . import db
from .models import LoudnessMeasurement, Station, StreamCheck, iso_utc
from .services import health
from .services.loudness import reset_loudness

api = Blueprint("api", __name__)

def error(message, status=400):
    return {"error": message}, status

@api.get("/stations")
def list_stations():
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("limit", 20, type=int), 1), 100)
    search = request.args.get("search")
    genre = request.args.get("genre")
    city = request.args.get("city")
    country = request.args.get("country")
    featured = request.args.get("featured")
    active = request.args.get("active")

    query = Station.query

    if search:
        q = f"%{search}%"
        query = query.filter(or_(Station.name.ilike(q), Station.city.ilike(q)))

    if city:
        query = query.filter(Station.city.ilike(city))

    if country:
        query = query.filter(Station.country.ilike(country))

    if genre:
        # `genres` is a JSON list. Match one element of it (case-insensitively) with SQLite's
        # json_each. The earlier `genres.contains([genre])` was a substring match on the JSON text,
        # so it only found stations whose *only* genre was the one asked for.
        query = query.filter(
            text("EXISTS (SELECT 1 FROM json_each(station.genres) "
                 "WHERE json_each.value = :genre COLLATE NOCASE)").bindparams(genre=genre)
        )

    if featured is not None:
        query = query.filter(Station.is_featured == (featured.lower() == "true"))

    if active is not None:
        query = query.filter(Station.is_active == (active.lower() == "true"))

    query = query.order_by(Station.is_featured.desc(), Station.name.asc())
    result = query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        "data": [s.to_dict() for s in result.items],
        "pagination": {
            "page": result.page,
            "limit": result.per_page,
            "total": result.total,
            "pages": result.pages
        }
    }

@api.get("/stations/featured")
def featured_stations():
    stations = Station.query.filter_by(is_featured=True, is_active=True).order_by(Station.name).all()
    return {"data": [s.to_dict() for s in stations]}

@api.get("/stations/<station_id>")
def get_station(station_id):
    station = db.session.get(Station, station_id)
    if not station:
        return error("Station not found", 404)
    return station.to_dict()

@api.post("/stations")
def create_station():
    data = request.get_json(silent=True) or {}
    required = ["id", "name"]
    missing = [x for x in required if not data.get(x)]
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}")

    if db.session.get(Station, data["id"]):
        return error("Station with this id already exists", 409)

    station = Station(
        id=data["id"],
        name=data["name"],
        frequency=data.get("frequency"),
        city=data.get("city"),
        country=data.get("country") or "Uganda",
        genres=data.get("genres", []),
        languages=data.get("languages", []),
        stream_url=data.get("streamUrl"),
        stream_type=data.get("streamType"),
        bitrate=data.get("bitrate"),
        website=data.get("website"),
        logo_url=data.get("logoUrl"),
        is_featured=data.get("isFeatured", False),
        is_active=data.get("isActive", True),
    )
    db.session.add(station)
    db.session.commit()
    return station.to_dict(), 201

@api.put("/stations/<station_id>")
def update_station(station_id):
    station = db.session.get(Station, station_id)
    if not station:
        return error("Station not found", 404)

    data = request.get_json(silent=True) or {}
    mapping = {
        "name": "name", "frequency": "frequency", "city": "city", "country": "country",
        "genres": "genres", "languages": "languages",
        "streamUrl": "stream_url", "streamType": "stream_type",
        "bitrate": "bitrate", "website": "website", "logoUrl": "logo_url",
        "isFeatured": "is_featured", "isActive": "is_active"
    }
    old_stream_url = station.stream_url
    was_active = station.is_active
    for key, attr in mapping.items():
        if key in data:
            setattr(station, attr, data[key])

    # The loudness worker measures a changed stream within about a minute. Readings taken on
    # the old stream would be wrong for the new one, so they are dropped.
    if station.stream_url != old_stream_url:
        reset_loudness(station)
        # Likewise the health worker checks the new URL on its next tick (within seconds).
        health.reset_health(station)
    elif station.is_active and not was_active:
        station.loudness_pending = True
        station.health_next_check_at = None

    db.session.commit()
    return station.to_dict()

@api.delete("/stations/<station_id>")
def delete_station(station_id):
    station = db.session.get(Station, station_id)
    if not station:
        return error("Station not found", 404)
    LoudnessMeasurement.query.filter_by(station_id=station_id).delete(synchronize_session=False)
    StreamCheck.query.filter_by(station_id=station_id).delete(synchronize_session=False)
    db.session.delete(station)
    db.session.commit()
    return {"message": "Station deleted", "id": station_id}

@api.get("/stations/<station_id>/loudness")
def station_loudness(station_id):
    """Read-only loudness detail for debugging an odd value: the published number and the
    raw readings (newest first) it was calculated from."""
    station = db.session.get(Station, station_id)
    if not station:
        return error("Station not found", 404)

    readings = (
        LoudnessMeasurement.query.filter_by(station_id=station_id)
        .order_by(LoudnessMeasurement.measured_at.desc(), LoudnessMeasurement.id.desc())
        .limit(50)
        .all()
    )
    return {
        "id": station.id,
        "loudnessLufs": station.loudness_lufs,
        "loudnessMeasuredAt": iso_utc(station.loudness_measured_at),
        "pending": bool(station.loudness_pending),
        "consecutiveFailures": station.loudness_fail_streak or 0,
        "history": [{"lufs": r.lufs, "measuredAt": iso_utc(r.measured_at)} for r in readings],
    }

@api.get("/stations/<station_id>/health")
def station_health(station_id):
    """Read-only stream health detail: the current status plus the last 50 probes (newest first)."""
    station = db.session.get(Station, station_id)
    if not station:
        return error("Station not found", 404)
    return health.health_detail(station)

@api.get("/streams/health")
def streams_health():
    """Admin table: one row per station (offline first) with status, last online, last error,
    30-day uptime and whether the stream is plain http (which iPhones block by default)."""
    return {"data": health.health_table()}

@api.post("/stations/<station_id>/check")
def check_one_station(station_id):
    station = db.session.get(Station, station_id)
    if not station:
        return error("Station not found", 404)

    result = health.check_station(station)
    return {
        "id": station.id,
        "reachable": result.ok,
        "streamStatus": station.stream_status,
        "error": result.error,
        "lastChecked": iso_utc(station.last_checked)
    }

@api.post("/stations/check-all")
def check_all_stations():
    stations = Station.query.filter_by(is_active=True).all()
    with_stream = [s for s in stations if s.stream_url]
    results = {sid: r.ok for sid, r in health.probe_stations(with_stream).items()}
    for station in stations:
        if not station.stream_url:  # nothing to probe: counts as unreachable, as before
            results[station.id] = health.check_station(station).ok
    data = [{"id": s.id, "reachable": results.get(s.id, False)} for s in stations]
    return {"data": data, "checked": len(data)}
