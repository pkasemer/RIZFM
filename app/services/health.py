"""Stream health: does each station's stream really work right now?

A URL that answers is not enough. A station counts as *working* only when

  1. the connection succeeds (DNS, TCP and TLS) within 8 seconds,
  2. the HTTP status is 200 (up to 5 redirects are followed),
  3. the Content-Type is audio, or an HLS / playlist type, and
  4. audio bytes really arrive: the first 16 KB are read within the same 8 seconds.

The probe is a plain GET (never HEAD: many Icecast / Shoutcast / Streamtheworld servers answer HEAD
wrongly) that is closed as soon as enough bytes have been read.

Status values and rules (see apply_result):
  online    last check passed.
  degraded  reachable but slow (first audio byte took over 4 s), or silent in the deep check.
  offline   3 failed checks in a row. One success brings a station straight back.
  unknown   never checked, or just added / its stream URL just changed.
A single failure does not change the status the app sees, so a one-off network hiccup never causes a
false warning.
"""

import hashlib
import http.client
import logging
import os
import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlsplit

from .. import db
from ..models import Station, StreamCheck, iso_utc
from . import alerts
from .stream_url import check_stream_url

log = logging.getLogger("health")

ONLINE, DEGRADED, OFFLINE, UNKNOWN = "online", "degraded", "offline", "unknown"

USER_AGENT = "Mozilla/5.0 (RIZFM health check)"
DEADLINE_SECONDS = 8.0        # connect + headers + first bytes, all within this
READ_BYTES = 16 * 1024        # how much audio to read before closing the connection
MIN_AUDIO_BYTES = 4 * 1024    # fewer bytes than this = connected but no real audio
MAX_REDIRECTS = 5
SLOW_MS = 4000                # first audio byte slower than this = degraded
OFFLINE_AFTER = 3             # consecutive failures before a station is offline
MAX_PARALLEL = 8              # probes at the same time
REMINDER_AFTER = timedelta(hours=24)
HISTORY_DAYS = 35             # probe history kept (the admin table shows 30-day uptime)

# Re-check intervals in seconds. Never below 60: each probe counts as a listener on the station's
# server and small hosts have low listener limits.
DEFAULT_HEALTHY_SECONDS = 300    # online / degraded
DEFAULT_SUSPECT_SECONDS = 60     # 1 or 2 failures so far: confirm or clear it quickly
DEFAULT_OFFLINE_SECONDS = 900    # confirmed offline: notice recovery without hammering the server

PLAYLIST_TYPES = {
    "audio/x-scpls", "audio/scpls", "application/pls+xml", "audio/x-mpegurl", "audio/mpegurl",
    "application/x-mpegurl", "application/vnd.apple.mpegurl",
}
UNTYPED = {"", "application/octet-stream", "binary/octet-stream", "application/x-octet-stream"}


@dataclass
class ProbeResult:
    ok: bool
    error: str | None = None       # dns, connect_timeout, connect_error, tls, http_<status>, not_audio,
                                   # no_data, too_many_redirects, bad_url
    response_ms: int | None = None  # time to the first audio byte


class _Fail(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


# --- the probe ---------------------------------------------------------------------------------

class _IcyResponse(http.client.HTTPResponse):
    """Accepts the old Shoutcast status line `ICY 200 OK`, which http.client rejects as invalid."""

    def _read_status(self):
        line = str(self.fp.readline(65537), "iso-8859-1")
        if not line:
            raise http.client.RemoteDisconnected("Remote end closed connection without response")
        if line.startswith("ICY "):
            line = "HTTP/1.0 " + line[4:]
        parts = line.split(None, 2)
        if len(parts) < 2 or not parts[0].startswith("HTTP/"):
            self._close_conn()
            raise http.client.BadStatusLine(line)
        try:
            status = int(parts[1])
        except ValueError:
            self._close_conn()
            raise http.client.BadStatusLine(line)
        return parts[0], status, parts[2].strip() if len(parts) > 2 else ""


_TLS_CONTEXT = None

# Forward-secret suites first, then the older static-RSA ones. Python's own defaults leave the RSA ones
# out, but some radio hosts (for example CBS FM's voscast server) offer nothing else, and phones play
# them fine. A health check that is stricter than a listener's phone reports false outages.
_TLS_CIPHERS = (
    "ECDH+AESGCM:ECDH+CHACHA20:ECDH+AES:DHE+AES:"
    "AES128-GCM-SHA256:AES256-GCM-SHA384:AES128-SHA256:AES256-SHA256:"
    "!aNULL:!eNULL:!MD5:!3DES"
)


def tls_context():
    """The TLS settings used for https probes. Certificates are still fully verified, TLS 1.2 or newer.

    `HEALTH_CA_BUNDLE` can point at a CA file, for machines where the system store is incomplete
    (corporate proxies, some Windows installs).
    """
    global _TLS_CONTEXT
    if _TLS_CONTEXT is None:
        context = ssl.create_default_context(cafile=os.getenv("HEALTH_CA_BUNDLE") or None)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ciphers(_TLS_CIPHERS)
        _TLS_CONTEXT = context
    return _TLS_CONTEXT


def _looks_like_audio(data):
    return (
        data.startswith((b"ID3", b"OggS", b"fLaC"))
        or (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)  # MPEG / AAC (ADTS) frame sync
        or b"\xff\xfb" in data[:4096] or b"\xff\xf1" in data[:4096] or b"\xff\xf9" in data[:4096]
    )


def _looks_like_html(data):
    head = data[:512].lstrip().lower()
    return head.startswith((b"<!doctype", b"<html", b"<?xml", b"{")) or b"<html" in head


def _playlist_entries(text):
    """Stream URLs in a .pls or .m3u playlist, in order."""
    entries = []
    for line in text.splitlines():
        line = line.strip()
        match = re.match(r"(?i)file\d+\s*=\s*(\S+)", line)
        if match:
            entries.append(match.group(1))
        elif line and not line.startswith(("#", "[")) and re.match(r"(?i)https?://", line):
            entries.append(line)
    return entries


def _elapsed_ms(started):
    return int((time.monotonic() - started) * 1000)


def _fetch(url, started, deadline):
    """GET one URL, following up to MAX_REDIRECTS redirects. Returns (response, connection, socket, url)."""
    current = url
    for _hop in range(MAX_REDIRECTS + 1):
        ok, _why = check_stream_url(current)
        if not ok:
            raise _Fail("bad_url")
        # urlsplit, not urlparse: urlparse cuts a trailing ";" off the path, and Shoutcast stream URLs
        # such as http://host:8000/; need it (without it the server sends its HTML status page).
        parsed = urlsplit(current)
        remaining = deadline - (time.monotonic() - started)
        if remaining <= 0:
            raise _Fail("connect_timeout")

        if parsed.scheme == "https":
            connection = http.client.HTTPSConnection(parsed.hostname, parsed.port, timeout=remaining,
                                                     context=tls_context())
        else:
            connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=remaining)
        connection.response_class = _IcyResponse
        target = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")
        try:
            connection.request("GET", target, headers={
                "User-Agent": USER_AGENT, "Icy-MetaData": "0", "Accept": "*/*", "Connection": "close",
            })
            # Keep our own reference: for a `Connection: close` reply http.client lets go of
            # connection.sock, and we still need it to bound each read by the deadline.
            sock = connection.sock
            response = connection.getresponse()
        except (socket.timeout, TimeoutError):
            connection.close()
            raise _Fail("connect_timeout")
        except socket.gaierror:
            connection.close()
            raise _Fail("dns")
        except ssl.SSLError as exc:
            connection.close()
            raise _Fail("connect_timeout" if "timed out" in str(exc).lower() else "tls")
        except (OSError, http.client.HTTPException):
            connection.close()
            raise _Fail("connect_error")

        if response.status in (301, 302, 303, 307, 308):
            location = response.getheader("Location")
            connection.close()
            if not location:
                raise _Fail(f"http_{response.status}")
            current = urljoin(current, location)
            continue
        if response.status != 200:
            connection.close()
            raise _Fail(f"http_{response.status}")
        return response, connection, sock, current
    raise _Fail("too_many_redirects")


def _read(response, sock, started, deadline, want):
    """Read up to `want` bytes before the deadline. Returns (data, ms to first byte)."""
    data = bytearray()
    first_byte_ms = None
    while len(data) < want:
        left = deadline - (time.monotonic() - started)
        if left <= 0:
            break
        try:
            if sock is not None:
                sock.settimeout(left)  # a stalled stream must not hold us past the deadline
            chunk = response.read1(4096)
        except (OSError, http.client.HTTPException):
            break  # timed out or dropped: judged by how many bytes did arrive
        if not chunk:
            break  # the server closed the stream
        if first_byte_ms is None:
            first_byte_ms = _elapsed_ms(started)
        data += chunk
    return bytes(data), first_byte_ms


def _probe(url, started, deadline, nested):
    response, connection, sock, final_url = _fetch(url, started, deadline)
    try:
        content_type = (response.getheader("Content-Type") or "").split(";")[0].strip().lower()
        is_playlist = content_type in PLAYLIST_TYPES
        is_audio = (content_type.startswith("audio/") or content_type in ("application/ogg", "application/x-ogg")) \
            and not is_playlist
        if not (is_playlist or is_audio or content_type in UNTYPED):
            raise _Fail("not_audio")  # an HTML or JSON answer: the server is up but the stream is not

        data, first_byte_ms = _read(response, sock, started, deadline, READ_BYTES)
    finally:
        connection.close()  # close the connection straight away

    if is_playlist:
        text = data.decode("utf-8", "replace")
        if "#EXT-X-" in text:  # HLS playlist: it is the stream
            return ProbeResult(True, response_ms=first_byte_ms)
        entries = _playlist_entries(text)
        if not entries or nested:
            raise _Fail("not_audio" if data else "no_data")
        # Otherwise the playlist only proves the playlist file exists: probe the stream it points to.
        return _probe(urljoin(final_url, entries[0]), started, deadline, nested=True)

    if len(data) < MIN_AUDIO_BYTES:
        raise _Fail("no_data")
    if content_type in UNTYPED:  # no useful Content-Type: judge by the bytes
        if _looks_like_html(data) or not _looks_like_audio(data):
            raise _Fail("not_audio")
    return ProbeResult(True, response_ms=first_byte_ms)


def probe_stream(url, deadline_seconds=None):
    """Probe one stream. Never raises; the outcome is in the returned ProbeResult."""
    started = time.monotonic()
    try:
        return _probe(url, started, deadline_seconds or DEADLINE_SECONDS, nested=False)
    except _Fail as failure:
        return ProbeResult(False, error=failure.code)
    except Exception as exc:  # a bug here must never stop the worker
        log.exception("probe crashed for %s", url)
        return ProbeResult(False, error="connect_error")


# --- turning results into a station status ------------------------------------------------------

def _seconds(name, default):
    try:
        return max(60, int(os.getenv(name, default)))
    except ValueError:
        return default


def station_offset(station_id):
    """A fixed 0-59 second offset per station, so the checks never all land in the same second."""
    return int(hashlib.md5(station_id.encode()).hexdigest(), 16) % 60


def next_interval(station):
    """Seconds until this station should be checked again, from its state right now."""
    if station.stream_status == OFFLINE:
        return _seconds("HEALTH_OFFLINE_INTERVAL", DEFAULT_OFFLINE_SECONDS) + station_offset(station.id)
    if station.stream_failures and station.stream_failures > 0:
        return _seconds("HEALTH_SUSPECT_INTERVAL", DEFAULT_SUSPECT_SECONDS)
    return _seconds("HEALTH_HEALTHY_INTERVAL", DEFAULT_HEALTHY_SECONDS) + station_offset(station.id)


def _utcnow():
    return datetime.now(timezone.utc)


def _as_utc(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def apply_result(station, result, now=None):
    """Update a station from one probe, record it, schedule the next one, and send any alert.

    Returns the list of alert events sent, for example ['offline'].
    """
    now = now or _utcnow()
    previous = station.stream_status or UNKNOWN
    events = []

    if result.ok:
        station.stream_failures = 0
        slow = result.response_ms is not None and result.response_ms > SLOW_MS
        station.stream_status = DEGRADED if (slow or station.stream_silent) else ONLINE
        station.last_error = "silence" if station.stream_silent else None
        station.last_online_at = now
        station.response_time_ms = result.response_ms
    else:
        station.stream_failures = (station.stream_failures or 0) + 1
        station.last_error = result.error
        station.response_time_ms = None
        # 1 or 2 failures keep the old status. Only the 3rd in a row makes a station offline.
        if station.stream_failures >= OFFLINE_AFTER:
            station.stream_status = OFFLINE

    went_offline = station.stream_status == OFFLINE and previous != OFFLINE
    recovered = previous == OFFLINE and station.stream_status != OFFLINE
    if went_offline:
        station.offline_since = now
        station.offline_reminded_at = now
    elif recovered:
        events.append(("recovered", f"[RECOVERED] {station.name} ({station.id}) is back online after "
                                    f"{_human_duration(now - _as_utc(station.offline_since or now))}."))
        station.offline_since = None
        station.offline_reminded_at = None
    elif station.stream_status == OFFLINE and station.offline_reminded_at is not None \
            and now - _as_utc(station.offline_reminded_at) >= REMINDER_AFTER:
        events.append(("still_offline", f"[STILL OFFLINE] {station.name} ({station.id}) has been offline for "
                                        f"{_human_duration(now - _as_utc(station.offline_since or now))}. "
                                        f"Its stream URL has probably changed and needs updating. "
                                        f"Last error: {station.last_error}."))
        station.offline_reminded_at = now
    if went_offline:
        events.insert(0, ("offline", f"[OFFLINE] {station.name} ({station.id}) failed {OFFLINE_AFTER} checks in a "
                                     f"row. Last error: {station.last_error}."))

    station.stream_reachable = None if station.stream_status == UNKNOWN else station.stream_status != OFFLINE
    station.last_checked = now
    station.health_next_check_at = now + timedelta(seconds=next_interval(station))
    db.session.add(StreamCheck(station_id=station.id, checked_at=now, ok=result.ok,
                               error=result.error, response_ms=result.response_ms))
    db.session.commit()

    for event, message in events:  # after the commit: a slow chat webhook must not hold the database
        alerts.notify(event, station, message)
    return [event for event, _ in events]


def _human_duration(delta):
    seconds = int(delta.total_seconds())
    if seconds < 3600:
        return f"{max(seconds // 60, 0)} min"
    if seconds < 86400:
        return f"{seconds // 3600} h {(seconds % 3600) // 60} min"
    return f"{seconds // 86400} d {(seconds % 86400) // 3600} h"


def mark_silent(station, silent):
    """Daily deep check result from the loudness job: a stream that is up but plays silence.

    The caller commits. A silent stream is 'degraded', never 'offline': it still plays.
    """
    if bool(station.stream_silent) == silent:
        return
    station.stream_silent = silent
    if silent:
        if station.stream_status == ONLINE:
            station.stream_status = DEGRADED
            station.stream_reachable = True
        if station.stream_status != OFFLINE:
            station.last_error = "silence"
    else:
        if station.stream_status == DEGRADED and (station.response_time_ms or 0) <= SLOW_MS:
            station.stream_status = ONLINE
        if station.last_error == "silence":
            station.last_error = None


def reset_health(station):
    """Forget the old stream's health and queue an immediate check.

    Used when a station's stream URL changes: what was learned about the old URL says nothing
    about the new one.
    """
    StreamCheck.query.filter_by(station_id=station.id).delete(synchronize_session=False)
    station.stream_status = UNKNOWN
    station.stream_reachable = None
    station.stream_failures = 0
    station.last_error = None
    station.stream_silent = False
    station.last_online_at = None
    station.response_time_ms = None
    station.offline_since = None
    station.offline_reminded_at = None
    station.health_next_check_at = None  # None = check as soon as possible


# --- running checks -----------------------------------------------------------------------------

def checkable_stations(now=None, only_due=True):
    """Active stations with a stream URL; by default only the ones whose next check time has come."""
    now = now or _utcnow()
    query = Station.query.filter(
        Station.is_active.is_(True), Station.stream_url.isnot(None), Station.stream_url != "",
    )
    if only_due:
        query = query.filter((Station.health_next_check_at.is_(None)) | (Station.health_next_check_at <= now))
    return query.order_by(Station.health_next_check_at.asc(), Station.id).all()


def probe_stations(stations, probe=None, max_parallel=MAX_PARALLEL):
    """Probe stations, at most `max_parallel` at once. Returns {station_id: ProbeResult}.

    Network probes run in threads; the database is only touched from the calling thread.
    """
    probe = probe or probe_stream
    urls = {station.id: station.stream_url for station in stations}
    results = {}
    if not urls:
        return results

    with ThreadPoolExecutor(max_workers=max(1, min(max_parallel, len(urls)))) as pool:
        futures = {pool.submit(probe, url): station_id for station_id, url in urls.items()}
        for future in as_completed(futures):
            station_id = futures[future]
            try:
                result = future.result()
            except Exception:
                log.exception("probe for %s raised", station_id)
                result = ProbeResult(False, error="connect_error")

            db.session.expire_all()  # the API process may have changed the station meanwhile
            station = db.session.get(Station, station_id)
            if station is None or station.stream_url != urls[station_id]:
                continue  # deleted, or its stream URL changed while probing: this result is stale
            apply_result(station, result)
            results[station_id] = result
    return results


def check_station(station, probe=None):
    """Probe one station now and record the result (manual check, CLI)."""
    probe = probe or probe_stream
    if not station.stream_url:
        result = ProbeResult(False, error="bad_url")
    else:
        result = probe(station.stream_url)
    apply_result(station, result)
    return result


def prune_history(now=None):
    """Delete probes older than HISTORY_DAYS. Returns how many rows went."""
    cutoff = (now or _utcnow()) - timedelta(days=HISTORY_DAYS)
    deleted = StreamCheck.query.filter(StreamCheck.checked_at < cutoff).delete(synchronize_session=False)
    db.session.commit()
    return deleted


# --- reporting ----------------------------------------------------------------------------------

def uptime_percent(station_id, days=30, now=None):
    """Share of probes in the last `days` that passed, or None if there are none."""
    since = (now or _utcnow()) - timedelta(days=days)
    rows = StreamCheck.query.filter(StreamCheck.station_id == station_id, StreamCheck.checked_at >= since)
    total = rows.count()
    if not total:
        return None
    return round(100.0 * rows.filter(StreamCheck.ok.is_(True)).count() / total, 1)


def health_detail(station, history_limit=50):
    checks = (
        StreamCheck.query.filter_by(station_id=station.id)
        .order_by(StreamCheck.checked_at.desc(), StreamCheck.id.desc())
        .limit(history_limit)
        .all()
    )
    return {
        "id": station.id,
        "streamStatus": station.stream_status or UNKNOWN,
        "streamReachable": station.stream_reachable,
        "lastChecked": iso_utc(station.last_checked),
        "lastOnlineAt": iso_utc(station.last_online_at),
        "responseTimeMs": station.response_time_ms,
        "consecutiveFailures": station.stream_failures or 0,
        "lastError": station.last_error,
        "offlineSince": iso_utc(station.offline_since),
        "nextCheckAt": iso_utc(station.health_next_check_at),
        "uptime30d": uptime_percent(station.id),
        "httpsOnly": bool(station.stream_url and station.stream_url.lower().startswith("https://")),
        "history": [
            {"checkedAt": iso_utc(c.checked_at), "ok": c.ok, "error": c.error, "responseMs": c.response_ms}
            for c in checks
        ],
    }


def health_table():
    """One row per station for the admin table. Offline first, then degraded, unknown, online."""
    order = {OFFLINE: 0, DEGRADED: 1, UNKNOWN: 2, ONLINE: 3}
    rows = []
    for station in Station.query.order_by(Station.id).all():
        rows.append({
            "id": station.id,
            "name": station.name,
            "isActive": bool(station.is_active),
            "streamStatus": station.stream_status or UNKNOWN,
            "lastOnlineAt": iso_utc(station.last_online_at),
            "lastError": station.last_error,
            "consecutiveFailures": station.stream_failures or 0,
            "uptime30d": uptime_percent(station.id),
            # iPhones block plain-HTTP streams by default, so these can pass a server-side probe
            # and still fail in the app.
            "httpOnly": bool(station.stream_url and station.stream_url.lower().startswith("http://")),
        })
    rows.sort(key=lambda r: (order.get(r["streamStatus"], 4), r["id"]))
    return rows
