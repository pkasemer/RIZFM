import os

from . import db
from .models import Station

# Public origin that serves app/static (logos live in app/static/logos/<station-id>.png).
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://rizfm.pkasemer.com").rstrip("/")


def logo_url_for(station_id):
    return f"{PUBLIC_BASE_URL}/static/logos/{station_id}.png"


STATIONS = [
    {
        "id": "capital-fm", "name": "Capital FM Uganda", "frequency": "91.3 FM",
        "city": "Kampala", "genres": ["Pop", "Adult Contemporary", "Talk"],
        "languages": ["English"], "streamUrl": "http://capitalfm.cloudrad.io/stream",
        "streamType": "mp3", "bitrate": 128, "website": "https://capitalradio.co.ug", "isFeatured": True
    },
    {
        "id": "beat-fm", "name": "Beat FM", "frequency": "96.3 FM", "city": "Kampala",
        "genres": ["Music", "Entertainment", "Talk"], "languages": ["English", "Luganda"],
        "streamUrl": "http://5230.cloudrad.io:8354/live", "streamType": "mp3", "bitrate": 128,
        "website": "https://beatradio.co.ug", "isFeatured": True
    },
    {
        "id": "kfm", "name": "KFM", "frequency": "93.3 FM", "city": "Kampala",
        "genres": ["News", "Talk", "Entertainment"], "languages": ["English"],
        "streamUrl": "http://radio.kfm.co.ug:8000/stream", "streamType": "mp3", "bitrate": 128,
        "website": "https://kfm.co.ug", "isFeatured": True
    },
    {
        "id": "galaxy-fm", "name": "Galaxy FM", "frequency": "100.2 FM", "city": "Kampala",
        "genres": ["Music", "Entertainment", "Urban"], "languages": ["English", "Luganda"],
        "streamUrl": "https://stream.zeno.fm/ahtmyttw5mftv", "streamType": "mp3", "bitrate": 128,
        "website": "https://galaxyfm.co.ug", "isFeatured": True
    },
    {
        "id": "radio-one", "name": "Radio One", "frequency": "90.0 FM", "city": "Kampala",
        "genres": ["Music", "News", "Talk"], "languages": ["English", "Luganda"],
        "streamUrl": "http://162.244.80.52:8740/stream", "streamType": "mp3", "bitrate": 128,
        "website": "https://radioonefm90.com", "isFeatured": True
    },
    {
        "id": "akaboozi", "name": "Akaboozi FM", "frequency": "87.9 FM", "city": "Kampala",
        "genres": ["News", "Talk", "Sports"], "languages": ["Luganda"],
        "streamUrl": "http://162.244.80.52:8732/stream", "streamType": "mp3", "bitrate": 64,
        "website": "https://akaboozi.com"
    },
    {
        "id": "next-radio", "name": "Next Radio", "frequency": "106.1 FM", "city": "Kampala",
        "genres": ["Music", "Entertainment", "Talk"], "languages": ["English", "Luganda"],
        "streamUrl": "https://stream-154.zeno.fm/lbca7zintcnuv", "streamType": "mp3",
        "bitrate": 128, "website": "https://nextradio.co.ug", "isFeatured": True
    },
    {
        "id": "radio-simba", "name": "Radio Simba", "frequency": "97.3 FM", "city": "Kampala",
        "genres": ["Music", "News", "Entertainment"], "languages": ["Luganda"],
        "streamUrl": "https://radiosimba-atunwadigital.streamguys1.com/radiosimba",
        "streamType": "mp3", "bitrate": 96, "website": "https://radiosimba.ug"
    },
    {
        "id": "radio-pacis", "name": "Radio Pacis", "frequency": "90.9 FM", "city": "Arua",
        "genres": ["Christian", "News", "Talk"], "languages": ["English", "Local Languages"],
        "streamUrl": "https://radiopacisuganda.radioca.st/stream", "streamType": "mp3",
        "bitrate": 64, "website": "https://radiopacis.org"
    },
    {
        "id": "sanyu-fm", "name": "Sanyu FM", "frequency": "88.2 FM", "city": "Kampala",
        "genres": ["Music", "Entertainment", "Talk"], "languages": ["English", "Luganda"],
        "streamUrl": "http://s44.myradiostream.com/8138/listen.mp3", "streamType": "mp3",
        "bitrate": 48, "website": "https://sanyufm.com"
    },
    {
        "id": "pearl-fm", "name": "Pearl FM", "frequency": "107.9 FM", "city": "Kampala",
        "genres": ["Music", "Entertainment"], "languages": ["English", "Luganda"],
        "streamUrl": "https://dc4.serverse.com/proxy/pearlfm/stream/1/", "streamType": "mp3",
        "bitrate": 64, "website": "https://pearlfmuganda.com"
    },
    {
        "id": "xfm", "name": "XFM Uganda", "frequency": "94.8 FM", "city": "Kampala",
        "genres": ["Music", "Pop", "Entertainment"], "languages": ["English"],
        "streamUrl": "http://stream.hydeinnovations.com:2020/stream/xfm/stream",
        "streamType": "mp3", "bitrate": 128, "website": "https://xfm.co.ug"
    },
    {
        "id": "crooze-fm", "name": "Crooze FM", "frequency": "91.2 FM", "city": "Fort Portal",
        "genres": ["Music", "Entertainment", "Talk"], "languages": ["English", "Local Languages"],
        "streamUrl": "https://stream-159.zeno.fm/vyxwdk08apxtv", "streamType": "mp3",
        "bitrate": 128, "website": "https://croozefm.com"
    },
    {
        "id": "radio-city", "name": "Radio City", "frequency": "97.0 FM", "city": "Kampala",
        "genres": ["Music", "Entertainment"], "languages": ["English"],
        "streamUrl": "https://cast1.asurahosting.com/proxy/richar16/stream",
        "streamType": "mp3", "bitrate": 128, "website": "https://radiocity.ug"
    },
    {
        "id": "busoga-one", "name": "Busoga One FM", "frequency": "90.6 FM", "city": "Jinja",
        "genres": ["News", "Talk", "Music"], "languages": ["English", "Lusoga"],
        "streamUrl": "https://stream.zeno.fm/xna2aad7gc9uv", "streamType": "mp3",
        "bitrate": 112, "website": "https://busogaone.com"
    },
    # --- Added later. Every stream below was probed and returned real audio data. ---
    {
        "id": "nrg-radio", "name": "NRG Radio Uganda", "frequency": "106.5 FM", "city": "Kampala",
        "genres": ["Afrobeats", "Pop", "Entertainment"], "languages": ["English"],
        "streamUrl": "https://dc4.serverse.com/proxy/nrgugstream/stream", "streamType": "mp3",
        "bitrate": 128, "website": "https://nrgug.radio", "isFeatured": True
    },
    {
        "id": "kiis-fm", "name": "KIIS FM", "frequency": "100.9 FM", "city": "Kampala",
        "genres": ["Pop", "Top 40", "Entertainment"], "languages": ["English"],
        "streamUrl": "http://14867.cloudrad.io:9224/live", "streamType": "mp3",
        "bitrate": 128, "isFeatured": True
    },
    {
        "id": "mega-fm", "name": "Mega FM Gulu", "frequency": "102.1 FM", "city": "Gulu",
        "genres": ["Music", "News", "Entertainment"], "languages": ["Luo", "English"],
        "streamUrl": "https://s2.myradiostream.com:5757/;", "streamType": "mp3",
        "bitrate": 128, "website": "https://megafmug.com", "isFeatured": True
    },
    {
        "id": "cbs-fm", "name": "CBS FM", "frequency": "88.8 FM", "city": "Kampala",
        "genres": ["News", "Talk", "Culture"], "languages": ["Luganda"],
        "streamUrl": "https://s5.voscast.com:9905/EMMANDUSO", "streamType": "mp3",
        "bitrate": 64, "website": "https://cbsfm.ug", "isFeatured": True
    },
    {
        "id": "bukedde-fm", "name": "Bukedde FM", "frequency": "100.5 FM", "city": "Kampala",
        "genres": ["News", "Talk", "Music"], "languages": ["Luganda"],
        "streamUrl": "https://stream.hydeinnovations.com:2020/stream/bukeddefm/stream",
        "streamType": "mp3", "bitrate": 128, "website": "https://www.bukedde.co.ug"
    },
    {
        "id": "dembe-fm", "name": "Dembe FM", "frequency": "90.4 FM", "city": "Kampala",
        "genres": ["Music", "Pop", "News"], "languages": ["English", "Luganda"],
        "streamUrl": "http://radio.dembefm.ug:8000/stream", "streamType": "mp3", "bitrate": 128
    },
    {
        "id": "radio-maria", "name": "Radio Maria Uganda", "frequency": "101.8 FM", "city": "Kampala",
        "genres": ["Christian", "Talk"], "languages": ["English", "Luganda"],
        "streamUrl": "https://dreamsiteradiocp2.com/proxy/rmuganda2?mp=/stream",
        "streamType": "aac", "bitrate": 64
    },
    {
        "id": "record-fm", "name": "Record FM", "frequency": "97.7 FM", "city": "Kampala",
        "genres": ["Music", "Entertainment", "Sports"], "languages": ["Luganda", "English"],
        "streamUrl": "https://a7.asurahosting.com/listen/record_fm_97.7/radio.mp3",
        "streamType": "mp3", "bitrate": 192
    },
    {
        "id": "baba-fm", "name": "Baba FM", "frequency": "87.7 FM", "city": "Jinja",
        "genres": ["Music", "News", "Talk"], "languages": ["Lusoga", "English"],
        "streamUrl": "https://stream.zeno.fm/ns28rp24dkhvv", "streamType": "mp3", "bitrate": 128
    },
    {
        "id": "christ-fm", "name": "Christ FM", "frequency": "91.6 FM", "city": "Kampala",
        "genres": ["Christian", "Talk"], "languages": ["English", "Luganda"],
        "streamUrl": "http://5.135.154.69:15664/;", "streamType": "mp3", "bitrate": 128
    },
    {
        "id": "voice-of-teso", "name": "Voice of Teso", "frequency": "88.4 FM", "city": "Soroti",
        "genres": ["News", "Talk", "Music"], "languages": ["Ateso", "English"],
        "streamUrl": "https://s46.webcastserver.com:12368/listen.mp3", "streamType": "mp3",
        "bitrate": 192
    },
    {
        "id": "open-gate-fm", "name": "Open Gate FM", "frequency": "103.2 FM", "city": "Mbale",
        "genres": ["News", "Community", "Music"], "languages": ["English"],
        "streamUrl": "http://139.162.195.139:8010/radio.mp3", "streamType": "mp3",
        "bitrate": 128, "website": "http://www.opengatefmmbale.com"
    },
    {
        "id": "radio-buddu", "name": "Radio Buddu", "frequency": "98.8 FM", "city": "Masaka",
        "genres": ["News", "Talk", "Music"], "languages": ["Luganda"],
        "streamUrl": "https://dc4.serverse.com/proxy/ccmxrgub/stream", "streamType": "mp3",
        "bitrate": 64
    }
]

def backfill_logos():
    """Give seeded stations that have no logo yet their bundled logo.

    Never overwrites a logoUrl that was set manually through the API.
    """
    changed = False
    for item in STATIONS:
        station = db.session.get(Station, item["id"])
        if station and not station.logo_url:
            station.logo_url = logo_url_for(item["id"])
            changed = True
    if changed:
        db.session.commit()


def seed_database():
    """Insert any seed station that is not in the database yet, then fill missing logos.

    Existing rows are never modified (apart from an empty logo), so edits made through
    the API survive restarts, and stations added to STATIONS later reach existing databases.
    """
    existing = {station_id for (station_id,) in db.session.query(Station.id).all()}
    for item in STATIONS:
        if item["id"] in existing:
            continue
        db.session.add(Station(
            id=item["id"], name=item["name"], frequency=item.get("frequency"),
            city=item.get("city"), genres=item.get("genres", []),
            languages=item.get("languages", []), stream_url=item.get("streamUrl"),
            stream_type=item.get("streamType"), bitrate=item.get("bitrate"),
            website=item.get("website"),
            logo_url=item.get("logoUrl") or logo_url_for(item["id"]),
            is_featured=item.get("isFeatured", False), is_active=item.get("isActive", True)
        ))
    db.session.commit()
    backfill_logos()
