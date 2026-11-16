import requests
from datetime import datetime, timezone

def check_stream(station):
    if not station.stream_url:
        station.stream_reachable = False
        station.last_checked = datetime.now(timezone.utc)
        return False

    try:
        response = requests.get(
            station.stream_url,
            headers={"User-Agent": "UgandaRadioAPI/1.0"},
            timeout=8,
            stream=True,
            allow_redirects=True,
        )
        reachable = response.status_code < 400
        response.close()
    except requests.RequestException:
        reachable = False

    station.stream_reachable = reachable
    station.last_checked = datetime.now(timezone.utc)
    return reachable
