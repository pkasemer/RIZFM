import os
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest

from app import create_app, db
from app import health_worker as worker
from app.models import Station, StreamCheck, iso_utc
from app.services import alerts, health
from app.seed import STATIONS
from app.services.health import ProbeResult

TOTAL_STATIONS = len(STATIONS)
ACTIVE_STATIONS = len([s for s in STATIONS if s.get("isActive", True)])  # the ones that are checked

OK = ProbeResult(True, response_ms=120)
AUDIO = b"\xff\xfb\x90\x00" * 6000  # 24 KB that looks like MP3 frames


def at(minutes=0.0, hours=0.0):
    return datetime(2026, 11, 17, 9, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes, hours=hours)


def fail(code="dns"):
    return ProbeResult(False, error=code)


@pytest.fixture(autouse=True)
def allow_localhost(monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_STREAM_HOSTS", "1")


@pytest.fixture
def sent(monkeypatch):
    events = []
    monkeypatch.setattr(alerts, "notify", lambda event, station, message: events.append((event, station.id, message)))
    return events


# --- a real local server to probe ---------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    seen = []  # (method, headers) of the last requests

    def log_message(self, *args):
        pass

    def reply(self, status, content_type, body=b"", extra=None):
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        port = self.server.server_address[1]
        Handler.seen.append((self.command, dict(self.headers), self.path))
        if path in ("/audio", "/;"):  # "/;" is how a Shoutcast v1 server is asked for the stream
            self.reply(200, "audio/mpeg", AUDIO)
        elif path == "/aacp":
            self.reply(200, "audio/aacp; charset=utf-8", AUDIO)
        elif path == "/ogg":
            self.reply(200, "application/ogg", b"OggS" + b"\x00" * 8000)
        elif path == "/slow-audio":
            time.sleep(1.3)
            self.reply(200, "audio/mpeg", AUDIO)
        elif path == "/html":
            self.reply(200, "text/html", b"<html><body>Station offline</body></html>")
        elif path == "/json":
            self.reply(200, "application/json", b'{"status": "offline"}')
        elif path == "/missing":
            self.reply(404, "text/html", b"not found")
        elif path == "/error":
            self.reply(503, "text/plain", b"busy")
        elif path == "/tiny":
            self.reply(200, "audio/mpeg", AUDIO[:1000])
        elif path == "/stall":  # connects, sends headers, then never any audio
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.end_headers()
            self.wfile.flush()
            time.sleep(4)
        elif path == "/hang":  # accepts the connection and then says nothing at all
            time.sleep(4)
        elif path == "/loop":
            self.reply(302, None, extra={"Location": "/loop"})
        elif path.startswith("/c") and path[2:].isdigit():  # /c0 -> /c1 -> ... -> /c6 -> /audio
            n = int(path[2:])
            self.reply(302, None, extra={"Location": f"/c{n + 1}" if n < 6 else "/audio"})
        elif path == "/hls":
            self.reply(200, "application/vnd.apple.mpegurl",
                       b"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:6\n#EXTINF:6.0,\nseg1.ts\n")
        elif path == "/pls":
            self.reply(200, "audio/x-scpls", f"[playlist]\nNumberOfEntries=1\nFile1=http://127.0.0.1:{port}/audio\n".encode())
        elif path == "/m3u":
            self.reply(200, "audio/x-mpegurl", f"#EXTM3U\n#EXTINF:-1,Station\nhttp://127.0.0.1:{port}/audio\n".encode())
        elif path == "/pls-dead":  # the playlist exists but the stream it points to is gone
            self.reply(200, "audio/x-scpls", f"[playlist]\nFile1=http://127.0.0.1:{port}/missing\n".encode())
        elif path == "/pls-empty":
            self.reply(200, "audio/x-scpls", b"[playlist]\nNumberOfEntries=0\n")
        elif path == "/pls-nested":  # a playlist that points to another playlist
            self.reply(200, "audio/x-scpls", f"[playlist]\nFile1=http://127.0.0.1:{port}/pls\n".encode())
        elif path == "/octet":
            self.reply(200, "application/octet-stream", b"ID3" + AUDIO)
        elif path == "/octet-html":
            self.reply(200, "application/octet-stream", b"<html>offline</html>" * 500)
        else:
            self.reply(404, "text/plain", b"?")


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def raw_server(responder):
    """A tiny TCP server: `responder(connection)` decides exactly what bytes to send."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)

    def serve():
        while True:
            try:
                connection, _ = listener.accept()
            except OSError:
                return
            try:
                connection.settimeout(2)
                try:
                    connection.recv(4096)
                except OSError:
                    pass
                responder(connection)
            finally:
                connection.close()

    threading.Thread(target=serve, daemon=True).start()
    return listener, listener.getsockname()[1]


# --- the probe ----------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "path, ok, error",
    [
        ("/audio", True, None),
        ("/;", True, None),                    # the trailing ";" of Shoutcast URLs must reach the server
        ("/aacp", True, None),                 # Content-Type parameters are ignored
        ("/ogg", True, None),
        ("/hls", True, None),                  # an HLS playlist is the stream
        ("/pls", True, None),                  # a playlist: the stream it points to is probed
        ("/m3u", True, None),
        ("/octet", True, None),                # no useful Content-Type: judged by the bytes
        ("/c2", True, None),                   # redirects are followed
        ("/html", False, "not_audio"),         # server up, stream not: typical "station offline" page
        ("/json", False, "not_audio"),
        ("/octet-html", False, "not_audio"),
        ("/missing", False, "http_404"),
        ("/error", False, "http_503"),
        ("/tiny", False, "no_data"),           # fewer than 4 KB of audio
        ("/pls-dead", False, "http_404"),      # the playlist exists, the stream does not
        ("/pls-empty", False, "not_audio"),
        ("/pls-nested", False, "not_audio"),   # playlists are followed one level only
        ("/loop", False, "too_many_redirects"),
        ("/c0", False, "too_many_redirects"),  # 7 hops: more than 5
    ],
)
def test_probe_outcomes(server, path, ok, error):
    result = health.probe_stream(server + path, deadline_seconds=5)
    assert (result.ok, result.error) == (ok, error)
    if ok:
        assert isinstance(result.response_ms, int) and result.response_ms >= 0


def test_probe_sends_a_plain_get_with_the_documented_headers(server):
    Handler.seen.clear()
    health.probe_stream(server + "/audio")
    method, headers, _ = Handler.seen[-1]
    # A HEAD would get a 501 from this server (as it would from many Icecast / Shoutcast hosts).
    assert method == "GET"
    assert headers["User-Agent"] == "Mozilla/5.0 (RIZFM health check)"
    assert headers["Icy-MetaData"] == "0"


def test_a_trailing_semicolon_in_the_stream_url_is_kept(server):
    Handler.seen.clear()
    assert health.probe_stream(server + "/;").ok
    assert Handler.seen[-1][2] == "/;"
    Handler.seen.clear()
    assert health.probe_stream(server + "/stream;?x=1").error == "http_404"  # (404 here, but the path arrived intact)
    assert Handler.seen[-1][2] == "/stream;?x=1"


def test_a_stream_that_connects_and_sends_nothing_is_dead_and_does_not_hold_the_probe(server):
    started = time.monotonic()
    result = health.probe_stream(server + "/stall", deadline_seconds=1.0)
    assert (result.ok, result.error) == (False, "no_data")
    assert time.monotonic() - started < 3  # bounded by the deadline, not by the server's 4 s sleep


def test_a_server_that_never_answers_is_a_connect_timeout(server):
    started = time.monotonic()
    result = health.probe_stream(server + "/hang", deadline_seconds=1.0)
    assert (result.ok, result.error) == (False, "connect_timeout")
    assert time.monotonic() - started < 3


def test_response_time_is_the_time_to_the_first_audio_byte(server):
    result = health.probe_stream(server + "/slow-audio", deadline_seconds=5)
    assert result.ok and result.response_ms >= 1200


def test_old_shoutcast_icy_status_lines_are_accepted():
    def icy(connection):
        connection.sendall(b"ICY 200 OK\r\nicy-name: Test FM\r\nContent-Type: audio/mpeg\r\n\r\n" + AUDIO)

    listener, port = raw_server(icy)
    try:
        assert health.probe_stream(f"http://127.0.0.1:{port}/;", deadline_seconds=5).ok
    finally:
        listener.close()


def test_connection_failures_get_their_own_codes():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    closed_port = listener.getsockname()[1]
    listener.close()  # nothing listens here any more

    assert health.probe_stream("http://no-such-host.invalid/stream", deadline_seconds=5).error == "dns"
    assert health.probe_stream(f"http://127.0.0.1:{closed_port}/", deadline_seconds=5).error == "connect_error"

    def not_tls(connection):  # answers a TLS hello with plain HTTP
        connection.sendall(b"HTTP/1.0 200 OK\r\n\r\n")

    listener, port = raw_server(not_tls)
    try:
        assert health.probe_stream(f"https://127.0.0.1:{port}/", deadline_seconds=5).error == "tls"
    finally:
        listener.close()


def test_only_public_http_urls_are_probed(server, monkeypatch):
    assert health.probe_stream("file:///etc/passwd").error == "bad_url"
    assert health.probe_stream("ftp://8.8.8.8/stream").error == "bad_url"
    monkeypatch.delenv("ALLOW_PRIVATE_STREAM_HOSTS")
    assert health.probe_stream(server + "/audio").error == "bad_url"  # localhost is not a public host


def test_a_redirect_to_an_internal_address_is_refused(monkeypatch):
    # The first hop is a (pretend) public host; it redirects to the cloud metadata address.
    def redirect(connection):
        connection.sendall(b"HTTP/1.0 302 Found\r\nLocation: http://169.254.169.254/latest/meta-data\r\n\r\n")

    listener, port = raw_server(redirect)
    real = health.check_stream_url
    monkeypatch.delenv("ALLOW_PRIVATE_STREAM_HOSTS")
    monkeypatch.setattr(health, "check_stream_url",
                        lambda url: (True, None) if f"127.0.0.1:{port}" in url else real(url))
    try:
        assert health.probe_stream(f"http://127.0.0.1:{port}/", deadline_seconds=5).error == "bad_url"
    finally:
        listener.close()


# --- status rules -------------------------------------------------------------------------------

def kfm():
    return db.session.get(Station, "kfm")


def test_a_new_station_is_unknown_with_null_fields():
    client = create_app().test_client()
    station = client.get("/api/v1/stations/kfm").json
    assert station["streamStatus"] == "unknown" and station["streamReachable"] is None
    assert station["lastChecked"] is None and station["lastOnlineAt"] is None and station["responseTimeMs"] is None


def test_one_or_two_failures_do_not_change_what_the_app_sees(sent):
    app = create_app()
    with app.app_context():
        station = kfm()
        health.apply_result(station, OK, now=at(0))
        assert station.stream_status == "online"

        health.apply_result(station, fail("dns"), now=at(1))
        assert (station.stream_status, station.stream_reachable, station.stream_failures) == ("online", True, 1)
        assert station.last_error == "dns" and sent == []

        health.apply_result(station, fail("connect_timeout"), now=at(2))
        assert (station.stream_status, station.stream_reachable, station.stream_failures) == ("online", True, 2)
        assert sent == []

        health.apply_result(station, fail("http_404"), now=at(3))  # the third in a row
        assert (station.stream_status, station.stream_reachable, station.stream_failures) == ("offline", False, 3)
        assert station.last_error == "http_404"
        assert [(event, station_id) for event, station_id, _ in sent] == [("offline", "kfm")]


def test_one_success_brings_an_offline_station_straight_back(sent):
    app = create_app()
    with app.app_context():
        station = kfm()
        for minute in range(3):
            health.apply_result(station, fail("http_404"), now=at(minute))
        assert station.stream_status == "offline"

        health.apply_result(station, OK, now=at(30))
        assert (station.stream_status, station.stream_reachable, station.stream_failures) == ("online", True, 0)
        assert station.last_error is None and station.response_time_ms == 120
        assert [event for event, _, _ in sent] == ["offline", "recovered"]
        assert "after 28 min" in sent[-1][2]  # went offline at minute 2, back at minute 30


def test_a_station_that_was_never_checked_stays_unknown_until_three_failures(sent):
    app = create_app()
    with app.app_context():
        station = kfm()
        health.apply_result(station, fail(), now=at(0))
        health.apply_result(station, fail(), now=at(1))
        assert (station.stream_status, station.stream_reachable) == ("unknown", None)
        health.apply_result(station, fail(), now=at(2))
        assert (station.stream_status, station.stream_reachable) == ("offline", False)


@pytest.mark.parametrize("ms, status", [(120, "online"), (4000, "online"), (4001, "degraded"), (9000, "degraded")])
def test_slow_first_audio_byte_is_degraded_but_still_reachable(ms, status):
    app = create_app()
    with app.app_context():
        station = kfm()
        health.apply_result(station, ProbeResult(True, response_ms=ms), now=at(0))
        assert (station.stream_status, station.stream_reachable) == (status, True)
        health.apply_result(station, ProbeResult(True, response_ms=100), now=at(5))
        assert station.stream_status == "online"  # fast again


def test_streamreachable_always_matches_the_status():
    app = create_app()
    with app.app_context():
        station = kfm()
        expected = {"online": True, "degraded": True, "offline": False, "unknown": None}
        for result in [OK, ProbeResult(True, response_ms=5000), fail(), fail(), fail(), OK]:
            health.apply_result(station, result)
            assert station.stream_reachable == expected[station.stream_status]


def test_alerts_are_for_state_changes_not_for_every_failed_probe(sent):
    app = create_app()
    with app.app_context():
        station = kfm()
        for minute in range(10):
            health.apply_result(station, fail(), now=at(minute))
        assert [event for event, _, _ in sent] == ["offline"]  # once, not 8 times


def test_a_reminder_goes_out_every_24_hours_while_a_station_stays_offline(sent):
    app = create_app()
    with app.app_context():
        station = kfm()
        for minute in range(3):
            health.apply_result(station, fail(), now=at(minute))
        sent.clear()

        health.apply_result(station, fail(), now=at(hours=23))
        assert sent == []
        health.apply_result(station, fail(), now=at(hours=24, minutes=5))
        assert [event for event, _, _ in sent] == ["still_offline"]
        assert "stream URL has probably changed" in sent[0][2]
        health.apply_result(station, fail(), now=at(hours=25))
        assert len(sent) == 1
        health.apply_result(station, fail(), now=at(hours=48, minutes=10))
        assert [event for event, _, _ in sent] == ["still_offline", "still_offline"]


def test_every_probe_is_recorded_and_uptime_is_the_share_that_passed():
    app = create_app()
    with app.app_context():
        station = kfm()
        for minute, result in enumerate([OK, OK, fail("http_404")]):
            health.apply_result(station, result, now=datetime.now(timezone.utc) - timedelta(minutes=10 - minute))
        checks = StreamCheck.query.filter_by(station_id="kfm").order_by(StreamCheck.checked_at).all()
        assert [(c.ok, c.error) for c in checks] == [(True, None), (True, None), (False, "http_404")]
        assert health.uptime_percent("kfm") == 66.7
        assert health.uptime_percent("capital-fm") is None  # no probes yet


def test_old_probe_history_is_pruned():
    app = create_app()
    with app.app_context():
        now = datetime.now(timezone.utc)
        db.session.add_all([
            StreamCheck(station_id="kfm", checked_at=now - timedelta(days=40), ok=True),
            StreamCheck(station_id="kfm", checked_at=now - timedelta(days=10), ok=True),
        ])
        db.session.commit()
        assert health.prune_history() == 1
        assert StreamCheck.query.count() == 1


# --- intervals ----------------------------------------------------------------------------------

def next_check(station):
    return iso_utc(station.health_next_check_at)


def test_recheck_intervals_follow_the_state_of_the_station():
    app = create_app()
    with app.app_context():
        station = kfm()
        offset = health.station_offset("kfm")

        health.apply_result(station, OK, now=at(0))  # healthy: 5 minutes
        assert next_check(station) == (at(0) + timedelta(seconds=300 + offset)).isoformat()

        health.apply_result(station, fail(), now=at(10))  # suspect: 1 minute, no offset
        assert next_check(station) == (at(10) + timedelta(seconds=60)).isoformat()
        health.apply_result(station, fail(), now=at(11))
        assert next_check(station) == (at(11) + timedelta(seconds=60)).isoformat()

        health.apply_result(station, fail(), now=at(12))  # confirmed offline: 15 minutes
        assert next_check(station) == (at(12) + timedelta(seconds=900 + offset)).isoformat()

        health.apply_result(station, OK, now=at(40))  # one success: back to every 5 minutes
        assert next_check(station) == (at(40) + timedelta(seconds=300 + offset)).isoformat()


def test_intervals_never_go_below_one_minute(monkeypatch):
    monkeypatch.setenv("HEALTH_SUSPECT_INTERVAL", "5")
    monkeypatch.setenv("HEALTH_HEALTHY_INTERVAL", "10")
    app = create_app()
    with app.app_context():
        station = kfm()
        health.apply_result(station, OK, now=at(0))
        assert (station.health_next_check_at - at(0).replace(tzinfo=None)).total_seconds() >= 60
        health.apply_result(station, fail(), now=at(5))
        assert (station.health_next_check_at - at(5).replace(tzinfo=None)).total_seconds() == 60


def test_checks_are_spread_out_with_a_fixed_offset_per_station():
    app = create_app()
    with app.app_context():
        offsets = {s.id: health.station_offset(s.id) for s in Station.query.all()}
    assert all(0 <= value < 60 for value in offsets.values())
    assert len(set(offsets.values())) > 15  # not all in the same second
    assert health.station_offset("kfm") == offsets["kfm"]  # stable between calls


# --- when checks run ----------------------------------------------------------------------------

def test_stations_are_checked_when_new_when_due_and_not_before():
    app = create_app()
    with app.app_context():
        total = len(health.checkable_stations())
        assert total == ACTIVE_STATIONS  # nothing has been checked: everything is due, straight away

        health.apply_result(kfm(), OK, now=datetime.now(timezone.utc))
        assert "kfm" not in {s.id for s in health.checkable_stations()}  # next check is in 5 minutes
        assert "kfm" in {s.id for s in health.checkable_stations(now=datetime.now(timezone.utc) + timedelta(minutes=6))}


def test_inactive_stations_and_stations_without_a_stream_are_not_checked():
    app = create_app()
    with app.app_context():
        kfm().is_active = False
        db.session.get(Station, "xfm").stream_url = None
        db.session.get(Station, "capital-fm").stream_url = ""
        db.session.commit()
        ids = {s.id for s in health.checkable_stations()}
        assert not ids & {"kfm", "xfm", "capital-fm"} and "beat-fm" in ids


def test_changing_the_stream_url_resets_health_and_queues_an_immediate_check():
    app = create_app()
    client = app.test_client()
    with app.app_context():
        for minute in range(3):
            health.apply_result(kfm(), fail("http_404"), now=at(minute))
        assert kfm().stream_status == "offline"

    client.put("/api/v1/stations/kfm", json={"name": "KFM Uganda"})  # other edits keep the status
    assert client.get("/api/v1/stations/kfm").json["streamStatus"] == "offline"

    client.put("/api/v1/stations/kfm", json={"streamUrl": "http://8.8.4.4/new"})
    station = client.get("/api/v1/stations/kfm").json
    assert (station["streamStatus"], station["streamReachable"], station["lastOnlineAt"]) == ("unknown", None, None)
    detail = client.get("/api/v1/stations/kfm/health").json
    assert detail["history"] == [] and detail["consecutiveFailures"] == 0 and detail["nextCheckAt"] is None
    with app.app_context():
        assert "kfm" in {s.id for s in health.checkable_stations()}  # due immediately, not on the next tick


def test_probing_never_runs_more_than_eight_at_once():
    app = create_app()
    state = {"now": 0, "max": 0}
    lock = threading.Lock()

    def fake(url):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(0.05)
        with lock:
            state["now"] -= 1
        return OK

    with app.app_context():
        results = health.probe_stations(health.checkable_stations(), probe=fake)
        assert len(results) == ACTIVE_STATIONS and state["max"] <= health.MAX_PARALLEL == 8
        # every active station was probed; an inactive one would be left alone
        assert {s.stream_status for s in Station.query.filter_by(is_active=True)} == {"online"}


def test_the_worker_checks_what_is_due_and_leaves_the_rest(monkeypatch):
    app = create_app()
    monkeypatch.setattr(health, "probe_stream", lambda url: OK)
    with app.app_context():
        assert len(worker.run_due()) == ACTIVE_STATIONS  # first pass: everything is new
        assert worker.run_due() == {}           # nothing is due again for 5 minutes
        later = datetime.now(timezone.utc) + timedelta(minutes=6)
        assert len(worker.run_due(now=later)) == ACTIVE_STATIONS


def test_the_worker_survives_a_failing_pass_and_stops_when_asked(monkeypatch):
    app = create_app()
    calls = []
    stop = threading.Event()

    def boom(now=None):
        calls.append(1)
        if len(calls) == 2:
            stop.set()
        raise RuntimeError("database is locked")

    monkeypatch.setattr(worker, "run_due", boom)
    worker.run_forever(app, stop=stop, tick_seconds=0, sleep=lambda seconds: None)
    assert len(calls) == 2


# --- the daily deep check -----------------------------------------------------------------------

def test_a_silent_stream_is_degraded_not_offline_and_stays_so_until_it_plays_again():
    app = create_app()
    with app.app_context():
        station = kfm()
        health.apply_result(station, OK, now=at(0))
        health.mark_silent(station, True)
        db.session.commit()
        assert (station.stream_status, station.stream_reachable, station.last_error) == ("degraded", True, "silence")

        health.apply_result(station, OK, now=at(5))  # an ordinary probe passes: still degraded, still silent
        assert (station.stream_status, station.last_error) == ("degraded", "silence")

        health.mark_silent(station, False)
        db.session.commit()
        assert (station.stream_status, station.last_error) == ("online", None)


def test_the_loudness_capture_is_the_deep_check_for_dead_air():
    from app.services import loudness
    from app.services.loudness import Capture

    app = create_app()
    with app.app_context():
        station = kfm()
        health.apply_result(station, OK, now=at(0))

        loudness.record_capture(station, Capture(float("-inf"), 30.0))  # decoded fine: nothing but silence
        assert (station.stream_status, station.last_error) == ("degraded", "silence")

        loudness.record_capture(station, Capture(None, 0.0, "timed out after 45s"))  # a failed run says nothing
        assert station.stream_status == "degraded"

        loudness.record_capture(station, Capture(-17.0, 30.0))  # audio again
        assert (station.stream_status, station.last_error) == ("online", None)


def test_a_silent_station_that_is_offline_stays_offline():
    app = create_app()
    with app.app_context():
        station = kfm()
        for minute in range(3):
            health.apply_result(station, fail("http_404"), now=at(minute))
        health.mark_silent(station, True)
        assert station.stream_status == "offline" and station.last_error == "http_404"


# --- the API ------------------------------------------------------------------------------------

def test_stations_expose_the_status_fields_and_keep_the_internal_ones_private():
    app = create_app()
    with app.app_context():
        health.apply_result(kfm(), ProbeResult(True, response_ms=250), now=at(0))
        health.apply_result(kfm(), fail("dns"), now=at(1))
    station = app.test_client().get("/api/v1/stations/kfm").json
    assert station["streamStatus"] == "online" and station["streamReachable"] is True
    assert station["lastChecked"] == "2026-11-17T09:01:00+00:00"   # explicit UTC, not a bare local-looking time
    assert station["lastOnlineAt"] == "2026-11-17T09:00:00+00:00"
    assert station["responseTimeMs"] is None                         # the latest probe failed
    # kept internal, as the guide asks
    assert not {"consecutiveFailures", "lastError", "streamFailures", "history"} & set(station)


def test_health_detail_endpoint():
    app = create_app()
    with app.app_context():
        for minute, result in enumerate([OK, fail("http_404")]):
            health.apply_result(kfm(), result, now=at(minute))
    client = app.test_client()
    detail = client.get("/api/v1/stations/kfm/health").json
    assert detail["streamStatus"] == "online" and detail["consecutiveFailures"] == 1
    assert detail["lastError"] == "http_404" and detail["uptime30d"] == 50.0  # 1 of 2 probes passed
    assert [(h["ok"], h["error"]) for h in detail["history"]] == [(False, "http_404"), (True, None)]  # newest first
    assert detail["httpsOnly"] is False  # kfm streams over plain http
    assert client.get("/api/v1/stations/nope/health").status_code == 404


def test_admin_table_lists_offline_first_and_flags_plain_http_streams():
    app = create_app()
    with app.app_context():
        for minute in range(3):
            health.apply_result(db.session.get(Station, "galaxy-fm"), fail("not_audio"), now=at(minute))
        health.apply_result(kfm(), OK, now=at(0))
    rows = app.test_client().get("/api/v1/streams/health").json["data"]
    assert len(rows) == TOTAL_STATIONS  # every station, inactive ones included (the admin table is the whole catalogue)
    assert rows[0]["id"] == "galaxy-fm" and rows[0]["streamStatus"] == "offline" and rows[0]["lastError"] == "not_audio"
    by_id = {r["id"]: r for r in rows}
    assert by_id["kfm"]["httpOnly"] is True and by_id["galaxy-fm"]["httpOnly"] is False  # https
    assert rows[-1]["streamStatus"] in ("online", "unknown")
    assert {"id", "name", "streamStatus", "lastOnlineAt", "lastError", "uptime30d", "httpOnly"} <= set(rows[0])


def test_manual_check_endpoints_use_the_same_probe_and_rules(monkeypatch):
    app = create_app()
    client = app.test_client()
    monkeypatch.setattr(health, "probe_stream", lambda url: OK if "kfm" in url else fail("http_404"))

    result = client.post("/api/v1/stations/kfm/check").json
    assert result["reachable"] is True and result["streamStatus"] == "online" and result["lastChecked"].endswith("+00:00")
    bad = client.post("/api/v1/stations/xfm/check").json
    assert bad["reachable"] is False and bad["error"] == "http_404"
    assert bad["streamStatus"] == "unknown"  # one failure does not change the status

    everything = client.post("/api/v1/stations/check-all").json
    assert everything["checked"] == ACTIVE_STATIONS
    reachable = {row["id"]: row["reachable"] for row in everything["data"]}
    assert reachable["kfm"] is True and reachable["xfm"] is False
    assert client.post("/api/v1/stations/nope/check").status_code == 404


def test_deleting_a_station_removes_its_probe_history():
    app = create_app()
    with app.app_context():
        health.apply_result(kfm(), OK)
    assert app.test_client().delete("/api/v1/stations/kfm").status_code == 200
    with app.app_context():
        assert StreamCheck.query.filter_by(station_id="kfm").count() == 0


# --- alerts -------------------------------------------------------------------------------------

def test_alerts_post_to_the_webhook_when_one_is_configured(monkeypatch):
    posted = []
    monkeypatch.setattr(alerts.requests, "post", lambda url, json, timeout: posted.append((url, json, timeout)))
    app = create_app()
    with app.app_context():
        monkeypatch.delenv("HEALTH_ALERT_WEBHOOK_URL", raising=False)
        alerts.notify("offline", kfm(), "[OFFLINE] KFM")
        assert posted == []  # no webhook: log only

        monkeypatch.setenv("HEALTH_ALERT_WEBHOOK_URL", "https://hooks.example/abc")
        alerts.notify("offline", kfm(), "[OFFLINE] KFM")
        url, body, timeout = posted[0]
        assert url == "https://hooks.example/abc" and timeout == 5
        assert body["text"] == body["content"] == "[OFFLINE] KFM"  # Slack-style and Discord-style
        assert body["event"] == "offline" and body["stationId"] == "kfm"


def test_a_broken_webhook_never_breaks_health_checking(monkeypatch):
    def broken(*args, **kwargs):
        raise alerts.requests.ConnectionError("no route")

    monkeypatch.setattr(alerts.requests, "post", broken)
    monkeypatch.setenv("HEALTH_ALERT_WEBHOOK_URL", "https://hooks.example/abc")
    app = create_app()
    with app.app_context():
        for minute in range(3):
            health.apply_result(kfm(), fail(), now=at(minute))  # goes offline, alert fails, no exception
        assert kfm().stream_status == "offline"


# --- upgrading a live database and the CLI ------------------------------------------------------

def test_existing_database_gets_the_health_columns_and_everything_is_due(tmp_path, monkeypatch):
    import sqlite3

    db_file = tmp_path / "live.db"
    conn = sqlite3.connect(db_file)
    # The schema as it was when every station returned null for streamReachable and lastChecked.
    conn.execute(
        "CREATE TABLE station (id VARCHAR(100) PRIMARY KEY, name VARCHAR(200) NOT NULL, frequency VARCHAR(50), "
        "city VARCHAR(100), country VARCHAR(100), genres JSON, languages JSON, stream_url TEXT, "
        "stream_type VARCHAR(50), bitrate INTEGER, website TEXT, logo_url TEXT, is_featured BOOLEAN, "
        "is_active BOOLEAN, stream_reachable BOOLEAN, last_checked DATETIME, created_at DATETIME, updated_at DATETIME)"
    )
    conn.execute("INSERT INTO station (id, name, country, stream_url, is_active) "
                 "VALUES ('kfm', 'My KFM', 'Uganda', 'http://8.8.8.8/kfm', 1)")
    conn.commit()
    conn.close()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    app = create_app()
    create_app()  # a second start (the API and a worker starting together) must not fail

    station = app.test_client().get("/api/v1/stations/kfm").json
    assert station["name"] == "My KFM"
    assert (station["streamStatus"], station["streamReachable"], station["lastChecked"]) == ("unknown", None, None)
    with app.app_context():
        assert "kfm" in {s.id for s in health.checkable_stations()}
        assert StreamCheck.query.count() == 0  # the history table exists


def test_cli_status_and_check_errors():
    from app.cli import streams_cli

    app = create_app()
    with app.app_context():
        for minute in range(3):
            health.apply_result(kfm(), fail("http_404"), now=at(minute))
    runner = app.test_cli_runner()

    result = runner.invoke(streams_cli, ["status"])
    assert result.exit_code == 0
    first = result.output.splitlines()[1]  # offline stations are listed first
    assert first.startswith("kfm ") and "offline" in first and "http_404" in first and "http only" in first

    missing = runner.invoke(streams_cli, ["check", "--station", "nope"])
    assert missing.exit_code != 0 and "No station" in missing.output


# --- TLS ----------------------------------------------------------------------------------------

def test_https_probes_accept_hosts_that_only_offer_static_rsa_ciphers_but_still_verify():
    import ssl

    context = health.tls_context()
    names = {cipher["name"] for cipher in context.get_ciphers()}
    # CBS FM's server offers only TLS 1.2 with RSA key exchange; phones play it, so the probe must too.
    assert names & {"AES128-GCM-SHA256", "AES256-GCM-SHA384"}
    assert any(name.startswith("ECDHE-") for name in names)  # forward-secret suites are still preferred
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2  # no TLS 1.0 / 1.1
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname  # certificates are still checked
    assert health.tls_context() is context  # built once


def test_a_ca_bundle_can_be_configured_for_machines_with_an_incomplete_system_store(monkeypatch):
    monkeypatch.setattr(health, "_TLS_CONTEXT", None)
    monkeypatch.setenv("HEALTH_CA_BUNDLE", os.path.join(os.path.dirname(__file__), "no-such-bundle.pem"))
    with pytest.raises(OSError):  # proves the setting is read (a real path would be used as the trust store)
        health.tls_context()
