"""Station loudness measurement.

The server only *reports* how loud each station is (integrated loudness in LUFS, ITU-R BS.1770 /
EBU R128). It never touches the audio: listeners connect straight to the station's own stream and
the mobile app turns loud stations down itself.

A reading is a ~30 second capture measured with ffmpeg's `ebur128` filter. Live programming varies
by a few dB, so the value we publish is the median of the last 5 accepted readings, taken at
different times of day (see `app/loudness_worker.py` for the schedule).
"""

import logging
import math
import os
import re
import statistics
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone

from .. import db
from ..models import LoudnessMeasurement, Station
from . import health
from .stream_url import check_stream_url  # noqa: F401  (re-exported: loudness.check_stream_url)

log = logging.getLogger("loudness")

CAPTURE_SECONDS = 30          # how much of the stream to read (ffmpeg -t, placed before -i)
TIMEOUT_SECONDS = 45          # hard limit per station; the ffmpeg process is killed after this
MIN_DECODED_SECONDS = 15      # a reading from less audio than this is rejected
LUFS_MIN = -45.0              # quieter than this is a decode problem, not a station
LUFS_MAX = -3.0               # louder than this is a decode problem, not a station
MEDIAN_OF = 5                 # published value = median of this many latest accepted readings
HISTORY_KEEP = 60             # readings kept per station for debugging
REVIEW_AFTER_FAILURES = 10    # consecutive failed runs before a station is flagged for review
MAX_PARALLEL = 4              # stations measured at the same time
MONO_GAIN_LU = 10 * math.log10(2)  # mono played on two speakers: +3.01 LU

USER_AGENT = "Mozilla/5.0 (RIZFM loudness)"
# Only network protocols. Stops a station URL such as file:///etc/passwd being opened by ffmpeg.
PROTOCOL_WHITELIST = "http,https,tcp,tls,crypto"

_INTEGRATED = re.compile(r"Integrated loudness:\s+I:\s+(-?[\d.]+|-inf)\s+LUFS", re.IGNORECASE)
_TIME = re.compile(r"time=(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")


@dataclass
class Capture:
    """What one ffmpeg run produced."""

    lufs: float | None
    seconds: float            # audio actually decoded
    error: str | None = None  # set when the run itself failed (timeout, bad exit code, blocked URL, ...)


# --- ffmpeg ------------------------------------------------------------------------------------

def build_command(stream_url):
    return [
        os.getenv("FFMPEG_BIN", "ffmpeg"),
        "-hide_banner", "-nostdin",
        "-user_agent", USER_AGENT,
        "-protocol_whitelist", PROTOCOL_WHITELIST,
        "-t", str(CAPTURE_SECONDS), "-i", stream_url,
        # Note there is deliberately no `-ac 2` here. It looks like it would measure a mono stream
        # "as heard" on both speakers, but ffmpeg's mono -> stereo upmix lowers each channel by 3 dB,
        # so it measures exactly the same as plain mono (checked on real mono stations).
        # Mono is handled explicitly instead: see MONO_GAIN_LU and input_is_mono().
        "-vn", "-af", "ebur128=framelog=quiet", "-f", "null", "-",
    ]


def parse_ffmpeg_output(output):
    """Return (integrated LUFS or None, seconds of audio decoded) from ffmpeg's stderr."""
    lufs = None
    matches = _INTEGRATED.findall(output)
    if matches:
        try:
            lufs = float(matches[-1])  # float("-inf") is valid and rejected later
        except ValueError:
            lufs = None
    seconds = max(
        (int(h) * 3600 + int(m) * 60 + float(s) for h, m, s in _TIME.findall(output)),
        default=0.0,
    )
    return lufs, seconds


def input_is_mono(output):
    """True if ffmpeg reports the stream's first audio track as mono.

    ffmpeg prints the input stream before the output one, so the first `Audio:` line is the input.
    """
    for line in output.splitlines():
        if "Audio:" in line:
            return re.search(r"\bmono\b", line) is not None
    return False


def reject_reason(lufs, seconds):
    """None if the reading is good, otherwise why it was thrown away."""
    if lufs is None:
        return "no loudness summary in ffmpeg output"
    if seconds < MIN_DECODED_SECONDS:
        return f"only {seconds:.1f}s of audio decoded (need {MIN_DECODED_SECONDS}s)"
    if not math.isfinite(lufs):
        return "silence (-inf LUFS)"
    if lufs > LUFS_MAX or lufs < LUFS_MIN:
        return f"{lufs} LUFS is outside {LUFS_MIN} to {LUFS_MAX}, almost certainly a decode problem"
    return None


def capture_loudness(stream_url, run=subprocess.run):
    """Capture and measure one stream. Never raises; failures come back in `Capture.error`."""
    ok, reason = check_stream_url(stream_url)
    if not ok:
        return Capture(None, 0.0, reason)

    try:
        # subprocess.run kills the child if the timeout expires, so ffmpeg never outlives its slot.
        proc = run(
            build_command(stream_url),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, errors="replace", timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return Capture(None, 0.0, f"timed out after {TIMEOUT_SECONDS}s")
    except FileNotFoundError:
        return Capture(None, 0.0, "ffmpeg is not installed")
    except OSError as exc:
        return Capture(None, 0.0, f"could not run ffmpeg: {exc}")

    output = proc.stderr or ""
    lufs, seconds = parse_ffmpeg_output(output)
    if lufs is not None and math.isfinite(lufs) and input_is_mono(output):
        # A phone plays a mono stream on both speakers, which is 10*log10(2) = 3.01 LU louder than
        # the single channel ffmpeg measured. The app's own measurements count mono this way.
        lufs += MONO_GAIN_LU
    if proc.returncode != 0:
        return Capture(lufs, seconds, f"ffmpeg exited with code {proc.returncode}")
    return Capture(lufs, seconds)


# --- storing results ---------------------------------------------------------------------------

def record_capture(station, capture, now=None):
    """Apply one run to a station. Returns True if the reading was accepted.

    A rejected run leaves the previously published value in place.
    """
    now = now or datetime.now(timezone.utc)
    reason = capture.error or reject_reason(capture.lufs, capture.seconds)
    station.loudness_pending = False

    # This capture doubles as stream health's deep check for dead air: a stream that is up but plays
    # silence is 'degraded'. Only a clean decode counts either way, never a run that failed.
    if capture.error is None:
        if capture.lufs == float("-inf") and capture.seconds >= MIN_DECODED_SECONDS:
            health.mark_silent(station, True)
        elif reason is None:
            health.mark_silent(station, False)

    if reason:
        station.loudness_fail_streak = (station.loudness_fail_streak or 0) + 1
        log.warning("loudness %s: rejected (%s) [%d in a row]", station.id, reason, station.loudness_fail_streak)
        if station.loudness_fail_streak % REVIEW_AFTER_FAILURES == 0:
            log.error("loudness %s: %d failed runs in a row, needs review (last good value %s kept)",
                      station.id, station.loudness_fail_streak, station.loudness_lufs)
        db.session.commit()
        return False

    db.session.add(LoudnessMeasurement(station_id=station.id, lufs=capture.lufs, measured_at=now))
    db.session.flush()

    latest = (
        LoudnessMeasurement.query.filter_by(station_id=station.id)
        .order_by(LoudnessMeasurement.measured_at.desc(), LoudnessMeasurement.id.desc())
    )
    recent = [row.lufs for row in latest.limit(MEDIAN_OF)]
    station.loudness_lufs = round(statistics.median(recent), 1)
    station.loudness_measured_at = now
    station.loudness_fail_streak = 0

    keep = [row.id for row in latest.limit(HISTORY_KEEP)]
    if len(keep) == HISTORY_KEEP:
        LoudnessMeasurement.query.filter(
            LoudnessMeasurement.station_id == station.id,
            LoudnessMeasurement.id.notin_(keep),
        ).delete(synchronize_session=False)

    db.session.commit()
    log.info("loudness %s: %.1f LUFS reading, published %.1f (median of %d)",
             station.id, capture.lufs, station.loudness_lufs, len(recent))
    return True


def reset_loudness(station):
    """Forget everything measured on the old stream and queue a fresh measurement.

    Used when a station is created, reactivated or its stream URL changes: a value measured on a
    different stream would be wrong.
    """
    LoudnessMeasurement.query.filter_by(station_id=station.id).delete(synchronize_session=False)
    station.loudness_lufs = None
    station.loudness_measured_at = None
    station.loudness_fail_streak = 0
    station.loudness_pending = True


# --- running a batch ---------------------------------------------------------------------------

def measurable_stations(only_pending=False):
    query = Station.query.filter(
        Station.is_active.is_(True),
        Station.stream_url.isnot(None),
        Station.stream_url != "",
    )
    if only_pending:
        query = query.filter(Station.loudness_pending.is_(True))
    return query.order_by(Station.id).all()


def measure_stations(stations, capture=capture_loudness, max_parallel=MAX_PARALLEL):
    """Measure stations, at most `max_parallel` at once. Returns {station_id: accepted}.

    ffmpeg runs in worker threads; the database is only touched from the calling thread.
    """
    urls = {station.id: station.stream_url for station in stations}
    results = {}
    if not urls:
        return results

    with ThreadPoolExecutor(max_workers=max(1, min(max_parallel, len(urls)))) as pool:
        futures = {pool.submit(capture, url): station_id for station_id, url in urls.items()}
        for future in as_completed(futures):
            station_id = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # a bug in one capture must not lose the others
                log.exception("loudness %s: unexpected error", station_id)
                result = Capture(None, 0.0, f"unexpected error: {exc}")

            db.session.expire_all()  # the API process may have changed the station meanwhile
            station = db.session.get(Station, station_id)
            if station is None or station.stream_url != urls[station_id]:
                continue  # deleted, or its stream changed while we were measuring: result is stale
            results[station_id] = record_capture(station, result)
    return results
