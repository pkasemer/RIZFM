import logging
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest

from app import create_app, db
from app.models import LoudnessMeasurement, Station, iso_utc
from app.services import loudness
from app.services.loudness import Capture

# What ffmpeg prints to stderr for a 30 second capture (progress lines trimmed).
FFMPEG_OUTPUT = """\
Input #0, mp3, from 'http://stream.example/live':
  Stream #0:0: Audio: mp3, 44100 Hz, stereo, fltp, 128 kb/s
size=N/A time=00:00:12.03 bitrate=N/A speed=1.0x
size=N/A time=00:00:29.97 bitrate=N/A speed=29.9x
[Parsed_ebur128_0 @ 0x55d0c8e0] Summary:

  Integrated loudness:
    I:         -17.4 LUFS
    Threshold: -27.6 LUFS

  Loudness range:
    LRA:         6.1 LU
"""

PUBLIC_URL = "http://8.8.8.8/stream"  # an IP literal needs no DNS lookup


def completed(stderr, returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr=stderr)


# --- parsing and validation --------------------------------------------------------------------

def test_parse_reads_integrated_loudness_and_decoded_seconds():
    assert loudness.parse_ffmpeg_output(FFMPEG_OUTPUT) == (-17.4, pytest.approx(29.97))


def test_parse_handles_silence_and_missing_summary():
    lufs, seconds = loudness.parse_ffmpeg_output(FFMPEG_OUTPUT.replace("-17.4", "-inf"))
    assert lufs == float("-inf") and seconds > 29
    assert loudness.parse_ffmpeg_output("Connection refused") == (None, 0.0)


def test_parse_adds_up_hours_and_minutes():
    assert loudness.parse_ffmpeg_output("time=01:02:03.50")[1] == pytest.approx(3723.5)


@pytest.mark.parametrize(
    "lufs, seconds, expected",
    [
        (-17.4, 30.0, None),
        (-17.4, 15.0, None),            # exactly the minimum
        (-17.4, 14.9, "only"),          # too little audio
        (None, 30.0, "no loudness"),
        (float("-inf"), 30.0, "silence"),
        (-0.9, 30.0, "outside"),        # AAC decoded as MP3 looks like this
        (-2.9, 30.0, "outside"),
        (-3.0, 30.0, None),             # boundary values are accepted
        (-45.0, 30.0, None),
        (-45.1, 30.0, "outside"),
    ],
)
def test_reject_reason(lufs, seconds, expected):
    reason = loudness.reject_reason(lufs, seconds)
    if expected is None:
        assert reason is None
    else:
        assert reason and expected in reason


def test_ffmpeg_command_follows_the_guide():
    cmd = loudness.build_command("http://x/stream")
    assert cmd[cmd.index("-t") + 1] == "30"
    # -t, -user_agent and -protocol_whitelist are input options: they must come before -i
    assert cmd.index("-t") < cmd.index("-i") and cmd.index("-user_agent") < cmd.index("-i")
    assert cmd.index("-protocol_whitelist") < cmd.index("-i")
    assert cmd[cmd.index("-i") + 1] == "http://x/stream"
    # `-ac 2` is a no-op for loudness (ffmpeg's upmix is -3 dB per channel), so mono is handled in code
    assert "-ac" not in cmd
    assert cmd[cmd.index("-af") + 1] == "ebur128=framelog=quiet"
    assert "file" not in cmd[cmd.index("-protocol_whitelist") + 1].split(",")


# --- stream URL safety --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://8.8.8.8/stream",
        "concat:a|b",
        "http://127.0.0.1:5000/health",
        "http://localhost/stream",
        "http://10.0.0.5/stream",
        "http://192.168.1.10/stream",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/stream",
        "",
        None,
    ],
)
def test_non_public_or_non_http_urls_are_never_measured(url):
    ok, reason = loudness.check_stream_url(url)
    assert not ok and reason

    def must_not_run(*args, **kwargs):
        raise AssertionError("ffmpeg must not be started for this URL")

    assert loudness.capture_loudness(url, run=must_not_run).error


def test_public_http_and_https_urls_are_allowed():
    assert loudness.check_stream_url("http://8.8.8.8/stream") == (True, None)
    assert loudness.check_stream_url("https://8.8.8.8:8443/live") == (True, None)


# --- running ffmpeg -----------------------------------------------------------------------------

def test_capture_returns_the_reading():
    capture = loudness.capture_loudness(PUBLIC_URL, run=lambda *a, **k: completed(FFMPEG_OUTPUT))
    assert capture.error is None and capture.lufs == -17.4 and capture.seconds == pytest.approx(29.97)


MONO_OUTPUT = FFMPEG_OUTPUT.replace("44100 Hz, stereo, fltp", "44100 Hz, mono, fltp")


def test_mono_streams_count_three_lu_louder_because_they_play_on_both_speakers():
    assert loudness.input_is_mono(MONO_OUTPUT) and not loudness.input_is_mono(FFMPEG_OUTPUT)
    # only the input stream counts, not the (always stereo) output line ffmpeg prints after it
    both = MONO_OUTPUT + "Output #0, null\n  Stream #0:0: Audio: pcm_s16le, 44100 Hz, stereo, s16\n"
    assert loudness.input_is_mono(both)
    assert not loudness.input_is_mono(FFMPEG_OUTPUT + "  Stream #0:0: Audio: pcm_s16le, 44100 Hz, mono\n")
    assert not loudness.input_is_mono("")

    mono = loudness.capture_loudness(PUBLIC_URL, run=lambda *a, **k: completed(MONO_OUTPUT))
    stereo = loudness.capture_loudness(PUBLIC_URL, run=lambda *a, **k: completed(FFMPEG_OUTPUT))
    assert stereo.lufs == -17.4
    assert mono.lufs == pytest.approx(-17.4 + 3.0103, abs=1e-3)


def test_mono_adjustment_does_not_turn_silence_or_missing_readings_into_something_else():
    silent = MONO_OUTPUT.replace("-17.4", "-inf")
    capture = loudness.capture_loudness(PUBLIC_URL, run=lambda *a, **k: completed(silent))
    assert capture.lufs == float("-inf") and loudness.reject_reason(capture.lufs, capture.seconds)
    nothing = loudness.capture_loudness(PUBLIC_URL, run=lambda *a, **k: completed("mono, no summary"))
    assert nothing.lufs is None


def test_the_adjusted_value_is_what_gets_range_checked():
    # -5.5 measured on a mono stream is -2.5 LU heard on two speakers: above the -3 limit, so rejected
    loud_mono = MONO_OUTPUT.replace("-17.4", "-5.5")
    capture = loudness.capture_loudness(PUBLIC_URL, run=lambda *a, **k: completed(loud_mono))
    assert capture.lufs == pytest.approx(-2.49, abs=0.01)
    assert "outside" in loudness.reject_reason(capture.lufs, capture.seconds)


def test_capture_reports_failures_instead_of_raising():
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=45)

    def missing(*args, **kwargs):
        raise FileNotFoundError("ffmpeg")

    assert "timed out" in loudness.capture_loudness(PUBLIC_URL, run=timeout).error
    assert "not installed" in loudness.capture_loudness(PUBLIC_URL, run=missing).error
    bad_exit = loudness.capture_loudness(PUBLIC_URL, run=lambda *a, **k: completed(FFMPEG_OUTPUT, returncode=1))
    assert "exited with code 1" in bad_exit.error  # a non-zero exit is rejected even with a summary


def test_capture_passes_a_hard_timeout_and_no_shell():
    seen = {}

    def run(cmd, **kwargs):
        seen.update(kwargs, cmd=cmd)
        return completed(FFMPEG_OUTPUT)

    loudness.capture_loudness(PUBLIC_URL, run=run)
    assert seen["timeout"] == 45 and isinstance(seen["cmd"], list) and "shell" not in seen


# --- storing readings ---------------------------------------------------------------------------

def good(lufs):
    return Capture(lufs, 30.0)


def reading_times(count):
    start = datetime(2026, 11, 17, 3, 0, tzinfo=timezone.utc)
    return [start + timedelta(hours=6 * i) for i in range(count)]


def test_published_value_is_the_median_of_the_last_five_readings():
    app = create_app()
    with app.app_context():
        station = db.session.get(Station, "kfm")
        values = [-10.0, -20.0, -30.0, -16.0, -17.0, -18.0]
        for value, when in zip(values, reading_times(len(values))):
            assert loudness.record_capture(station, good(value), now=when)
        # median of the last 5 (-20, -30, -16, -17, -18) is -18.0; including -10 would give -17.5
        assert station.loudness_lufs == -18.0
        assert iso_utc(station.loudness_measured_at) == reading_times(6)[-1].isoformat()
        assert LoudnessMeasurement.query.filter_by(station_id="kfm").count() == 6  # raw history kept


def test_published_value_has_one_decimal_place_and_an_even_count_averages_the_middle_two():
    app = create_app()
    with app.app_context():
        station = db.session.get(Station, "kfm")
        loudness.record_capture(station, good(-17.04), now=reading_times(2)[0])
        assert station.loudness_lufs == -17.0  # rounded for publishing...
        assert LoudnessMeasurement.query.one().lufs == -17.04  # ...but the raw reading is kept as measured

        loudness.record_capture(station, good(-17.4), now=reading_times(2)[1])
        # two readings: the median is the average of the middle two, (-17.04 + -17.4) / 2 = -17.22
        assert station.loudness_lufs == -17.2


def test_a_rejected_run_keeps_the_previous_value_and_counts_the_failure():
    app = create_app()
    with app.app_context():
        station = db.session.get(Station, "kfm")
        loudness.record_capture(station, good(-16.5))
        before = station.loudness_measured_at

        assert not loudness.record_capture(station, Capture(-0.9, 30.0))
        assert not loudness.record_capture(station, Capture(None, 0.0, "timed out after 45s"))
        assert station.loudness_lufs == -16.5 and station.loudness_measured_at == before
        assert station.loudness_fail_streak == 2
        assert LoudnessMeasurement.query.filter_by(station_id="kfm").count() == 1

        assert loudness.record_capture(station, good(-17.0))
        assert station.loudness_fail_streak == 0  # a success ends the streak


def test_ten_failures_in_a_row_flag_the_station_but_keep_its_last_good_value(caplog):
    app = create_app()
    with app.app_context():
        station = db.session.get(Station, "kfm")
        loudness.record_capture(station, good(-16.5))
        with caplog.at_level(logging.WARNING, logger="loudness"):
            for _ in range(10):
                loudness.record_capture(station, Capture(None, 0.0, "stream is down"))
        assert station.loudness_fail_streak == 10
        assert station.loudness_lufs == -16.5
        assert any("needs review" in r.message for r in caplog.records if r.levelno == logging.ERROR)


def test_history_is_trimmed():
    app = create_app()
    with app.app_context():
        station = db.session.get(Station, "kfm")
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(loudness.HISTORY_KEEP + 5):
            loudness.record_capture(station, good(-17.0), now=start + timedelta(hours=i))
        assert LoudnessMeasurement.query.filter_by(station_id="kfm").count() == loudness.HISTORY_KEEP


# --- the API ------------------------------------------------------------------------------------

def test_stations_expose_the_two_loudness_fields_and_nothing_else_changed():
    client = create_app().test_client()
    station = client.get("/api/v1/stations/kfm").json
    assert station["loudnessLufs"] is None and station["loudnessMeasuredAt"] is None
    assert {"id", "name", "streamUrl", "country", "lastChecked"} <= set(station)  # existing shape intact
    listed = client.get("/api/v1/stations?limit=100").json["data"]
    assert all("loudnessLufs" in s and "loudnessMeasuredAt" in s for s in listed)


def test_api_returns_the_published_value_with_a_utc_timestamp():
    app = create_app()
    with app.app_context():
        loudness.record_capture(db.session.get(Station, "kfm"), good(-16.5), now=reading_times(1)[0])
    station = app.test_client().get("/api/v1/stations/kfm").json
    assert station["loudnessLufs"] == -16.5
    assert station["loudnessMeasuredAt"] == "2026-11-17T03:00:00+00:00"


def test_loudness_cannot_be_written_through_the_api():
    client = create_app().test_client()
    assert client.put("/api/v1/stations/kfm", json={"loudnessLufs": -5.0}).json["loudnessLufs"] is None
    created = client.post("/api/v1/stations", json={"id": "z-fm", "name": "Z FM", "loudnessLufs": -9.9})
    assert created.status_code == 201 and created.json["loudnessLufs"] is None


def test_changing_the_stream_url_discards_old_readings_and_queues_a_new_measurement():
    app = create_app()
    client = app.test_client()
    with app.app_context():
        station = db.session.get(Station, "kfm")
        loudness.record_capture(station, good(-16.5))
        assert station.loudness_pending is False

    # Editing something else leaves the measurement alone.
    client.put("/api/v1/stations/kfm", json={"name": "KFM Uganda"})
    assert client.get("/api/v1/stations/kfm").json["loudnessLufs"] == -16.5
    # Sending the same URL again is not a change either.
    same_url = client.get("/api/v1/stations/kfm").json["streamUrl"]
    client.put("/api/v1/stations/kfm", json={"streamUrl": same_url})
    assert client.get("/api/v1/stations/kfm").json["loudnessLufs"] == -16.5

    client.put("/api/v1/stations/kfm", json={"streamUrl": "http://8.8.4.4/new-stream"})
    detail = client.get("/api/v1/stations/kfm/loudness").json
    assert detail["loudnessLufs"] is None and detail["loudnessMeasuredAt"] is None
    assert detail["pending"] is True and detail["history"] == []


def test_new_stations_start_pending_and_unmeasured():
    client = create_app().test_client()
    client.post("/api/v1/stations", json={"id": "new-fm", "name": "New FM", "streamUrl": "http://8.8.8.8/s"})
    detail = client.get("/api/v1/stations/new-fm/loudness").json
    assert detail["pending"] is True and detail["loudnessLufs"] is None


def test_loudness_detail_lists_readings_newest_first_and_404s_for_unknown_stations():
    app = create_app()
    with app.app_context():
        station = db.session.get(Station, "kfm")
        for value, when in zip([-16.0, -17.0, -18.0], reading_times(3)):
            loudness.record_capture(station, good(value), now=when)
    client = app.test_client()
    detail = client.get("/api/v1/stations/kfm/loudness").json
    assert [h["lufs"] for h in detail["history"]] == [-18.0, -17.0, -16.0]
    assert detail["consecutiveFailures"] == 0 and detail["loudnessLufs"] == -17.0
    assert client.get("/api/v1/stations/nope/loudness").status_code == 404


def test_deleting_a_station_removes_its_readings():
    app = create_app()
    with app.app_context():
        loudness.record_capture(db.session.get(Station, "kfm"), good(-16.5))
    assert app.test_client().delete("/api/v1/stations/kfm").status_code == 200
    with app.app_context():
        assert LoudnessMeasurement.query.filter_by(station_id="kfm").count() == 0


# --- running a batch ----------------------------------------------------------------------------

def test_batch_measures_every_station_and_never_more_than_four_at_once():
    app = create_app()
    state = {"now": 0, "max": 0}
    lock = threading.Lock()

    def fake_capture(url):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(0.05)
        with lock:
            state["now"] -= 1
        return good(-17.0)

    with app.app_context():
        stations = loudness.measurable_stations()[:12]
        results = loudness.measure_stations(stations, capture=fake_capture)
        assert len(results) == 12 and all(results.values())
        assert state["max"] <= loudness.MAX_PARALLEL
        assert all(db.session.get(Station, s.id).loudness_lufs == -17.0 for s in stations)


def test_one_crashing_capture_does_not_lose_the_others():
    app = create_app()

    def flaky(url):
        if "capitalfm" in url:
            raise RuntimeError("boom")
        return good(-17.0)

    with app.app_context():
        stations = [db.session.get(Station, i) for i in ("capital-fm", "kfm")]
        results = loudness.measure_stations(stations, capture=flaky)
        assert results == {"capital-fm": False, "kfm": True}
        assert db.session.get(Station, "capital-fm").loudness_fail_streak == 1


def test_inactive_stations_and_stations_without_a_stream_are_skipped():
    app = create_app()
    with app.app_context():
        db.session.get(Station, "kfm").is_active = False
        db.session.get(Station, "xfm").stream_url = None
        db.session.get(Station, "capital-fm").stream_url = ""
        db.session.commit()
        ids = {s.id for s in loudness.measurable_stations()}
        assert not ids & {"kfm", "xfm", "capital-fm"} and "beat-fm" in ids


# --- the worker's schedule ----------------------------------------------------------------------

from app import loudness_worker as worker  # noqa: E402


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_parse_slots():
    assert worker.parse_slots("23:00, 06:00,12:00,18:00,06:00") == [(6, 0), (12, 0), (18, 0), (23, 0)]
    assert worker.parse_slots("7") == [(7, 0)]
    for bad in ("", "25:00", "12:99", "noon"):
        with pytest.raises(ValueError):
            worker.parse_slots(bad)


def test_next_slot_is_in_east_africa_time():
    slots = worker.parse_slots(worker.DEFAULT_SLOTS)
    # 04:00 UTC is 07:00 in Kampala, so the next run is 12:00 EAT = 09:00 UTC
    assert worker.next_slot(utc(2026, 11, 17, 4, 0), slots) == utc(2026, 11, 17, 9, 0)
    # a slot that has just arrived is not "next": it moves on to the following one
    assert worker.next_slot(utc(2026, 11, 17, 9, 0), slots) == utc(2026, 11, 17, 15, 0)
    # after the last slot of the day (23:00 EAT = 20:00 UTC) it rolls to 06:00 EAT tomorrow = 03:00 UTC
    assert worker.next_slot(utc(2026, 11, 17, 20, 30), slots) == utc(2026, 11, 18, 3, 0)
    # 22:30 UTC is already 01:30 EAT on the 18th: next is 06:00 EAT = 03:00 UTC the same UTC day
    assert worker.next_slot(utc(2026, 11, 17, 22, 30), slots) == utc(2026, 11, 18, 3, 0)


def test_pending_pass_only_measures_stations_waiting_for_a_measurement(monkeypatch):
    app = create_app()
    seen = []
    monkeypatch.setattr(loudness, "measure_stations", lambda stations, **kw: seen.append([s.id for s in stations]) or {})
    with app.app_context():
        # a fresh database: every seeded station is pending
        worker.run_pass(only_pending=True)
        assert len(seen[-1]) == len(loudness.measurable_stations())

        Station.query.update({Station.loudness_pending: False})
        db.session.get(Station, "kfm").loudness_pending = True
        db.session.commit()
        worker.run_pass(only_pending=True)
        assert seen[-1] == ["kfm"]

        worker.run_pass(only_pending=False)  # a scheduled pass measures everything again
        assert len(seen[-1]) == len(loudness.measurable_stations())


def test_the_worker_survives_a_failing_pass_and_stops_when_asked(monkeypatch):
    app = create_app()
    calls = []
    stop = threading.Event()

    def boom(only_pending):
        calls.append(only_pending)
        if len(calls) == 2:
            stop.set()
        raise RuntimeError("database is locked")

    monkeypatch.setattr(worker, "run_pass", boom)
    worker.run_forever(app, stop=stop, poll_seconds=0, sleep=lambda seconds: None)
    assert calls == [True, True]  # kept going after the first exception, stopped after the second


# --- upgrading a live database ------------------------------------------------------------------

def test_existing_database_gets_the_loudness_columns_and_is_queued_for_measurement(tmp_path, monkeypatch):
    import sqlite3

    db_file = tmp_path / "live.db"
    conn = sqlite3.connect(db_file)
    # The schema as deployed before loudness existed (it already has the country column).
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
    app = create_app()  # runs the migration
    create_app()        # and a second start (or the worker starting alongside) must not fail

    station = app.test_client().get("/api/v1/stations/kfm").json
    assert station["name"] == "My KFM" and station["loudnessLufs"] is None
    detail = app.test_client().get("/api/v1/stations/kfm/loudness").json
    assert detail["pending"] is True and detail["consecutiveFailures"] == 0
    with app.app_context():
        assert LoudnessMeasurement.query.count() == 0  # the history table exists


# --- command line -------------------------------------------------------------------------------

def test_cli_status_and_measure_errors():
    from app.cli import loudness_cli

    app = create_app()
    with app.app_context():
        station = db.session.get(Station, "kfm")
        loudness.record_capture(station, good(-16.5))
        station.loudness_fail_streak = 10
        db.session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(loudness_cli, ["status"])
    assert result.exit_code == 0
    kfm_line = next(line for line in result.output.splitlines() if line.startswith("kfm "))
    assert "-16.5" in kfm_line and "NEEDS REVIEW" in kfm_line

    missing = runner.invoke(loudness_cli, ["measure", "--station", "nope"])
    assert missing.exit_code != 0 and "No station" in missing.output
