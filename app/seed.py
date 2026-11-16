from . import db
from .models import Station

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
    }
]

def seed_database():
    if db.session.query(Station).count() > 0:
        return
    for item in STATIONS:
        db.session.add(Station(
            id=item["id"], name=item["name"], frequency=item.get("frequency"),
            city=item.get("city"), genres=item.get("genres", []),
            languages=item.get("languages", []), stream_url=item.get("streamUrl"),
            stream_type=item.get("streamType"), bitrate=item.get("bitrate"),
            website=item.get("website"), logo_url=item.get("logoUrl"),
            is_featured=item.get("isFeatured", False), is_active=item.get("isActive", True)
        ))
    db.session.commit()
