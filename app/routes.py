from flask import Blueprint, request
from sqlalchemy import or_
from . import db
from .models import Station
from .services.stream_checker import check_stream

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
        query = query.filter(Station.genres.contains([genre]))

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
    for key, attr in mapping.items():
        if key in data:
            setattr(station, attr, data[key])

    db.session.commit()
    return station.to_dict()

@api.delete("/stations/<station_id>")
def delete_station(station_id):
    station = db.session.get(Station, station_id)
    if not station:
        return error("Station not found", 404)
    db.session.delete(station)
    db.session.commit()
    return {"message": "Station deleted", "id": station_id}

@api.post("/stations/<station_id>/check")
def check_one_station(station_id):
    station = db.session.get(Station, station_id)
    if not station:
        return error("Station not found", 404)

    reachable = check_stream(station)
    db.session.commit()
    return {
        "id": station.id,
        "reachable": reachable,
        "lastChecked": station.last_checked.isoformat()
    }

@api.post("/stations/check-all")
def check_all_stations():
    stations = Station.query.filter_by(is_active=True).all()
    results = []
    for station in stations:
        results.append({
            "id": station.id,
            "reachable": check_stream(station)
        })
    db.session.commit()
    return {"data": results, "checked": len(results)}
