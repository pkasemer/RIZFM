"""Background job that keeps every station's loudness up to date.

Run it as its own process (the `loudness-worker` service in docker-compose.yml):

    python -m app.loudness_worker

What it does:
  * 4 times a day (06:00, 12:00, 18:00 and 23:00 East Africa Time by default) it measures every
    active station, so the published median covers different programmes: music, talk, adverts.
  * Every `LOUDNESS_POLL_SECONDS` it also measures stations flagged `loudness_pending`: new
    stations, stations whose stream URL changed, and stations that have never been measured.
  * At most 4 stations are measured at once, each with a hard 45 second limit.

A failed run is simply logged and retried at the next slot.
"""

import logging
import os
import signal
import threading
from datetime import datetime, timedelta, timezone

from .services import loudness

log = logging.getLogger("loudness")

# East Africa Time is UTC+3 all year (no daylight saving), so a fixed offset is exact.
EAT = timezone(timedelta(hours=3), "EAT")
DEFAULT_SLOTS = "06:00,12:00,18:00,23:00"
DEFAULT_POLL_SECONDS = 30


def parse_slots(spec):
    """'06:00,12:00' -> [(6, 0), (12, 0)], sorted, in East Africa Time."""
    slots = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        hours, _, minutes = part.partition(":")
        hour, minute = int(hours), int(minutes or 0)
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError(f"bad time {part!r} in LOUDNESS_SLOTS")
        slots.append((hour, minute))
    if not slots:
        raise ValueError("LOUDNESS_SLOTS needs at least one HH:MM time")
    return sorted(set(slots))


def next_slot(after, slots):
    """The first slot strictly after `after` (a timezone-aware datetime), as a UTC datetime."""
    local = after.astimezone(EAT)
    for day_offset in (0, 1):
        day = local.date() + timedelta(days=day_offset)
        for hour, minute in slots:
            candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=EAT)
            if candidate > local:
                return candidate.astimezone(timezone.utc)
    raise AssertionError("unreachable: tomorrow always has a slot")


def run_pass(only_pending):
    """One batch: all active stations, or only the ones waiting for a first/new measurement."""
    stations = loudness.measurable_stations(only_pending=only_pending)
    if not stations:
        return {}
    log.info("measuring %d station(s)%s", len(stations), " (pending only)" if only_pending else " (scheduled)")
    results = loudness.measure_stations(stations)
    accepted = sum(results.values())
    log.info("done: %d accepted, %d rejected", accepted, len(results) - accepted)
    return results


def run_forever(app, stop=None, poll_seconds=None, sleep=None):
    stop = stop or threading.Event()
    poll = poll_seconds or float(os.getenv("LOUDNESS_POLL_SECONDS", DEFAULT_POLL_SECONDS))
    slots = parse_slots(os.getenv("LOUDNESS_SLOTS", DEFAULT_SLOTS))
    upcoming = next_slot(datetime.now(timezone.utc), slots)
    log.info("loudness worker started; scheduled runs at %s EAT, next at %s",
             ", ".join(f"{h:02d}:{m:02d}" for h, m in slots), upcoming.astimezone(EAT).strftime("%Y-%m-%d %H:%M"))

    while not stop.is_set():
        try:
            with app.app_context():
                now = datetime.now(timezone.utc)
                if now >= upcoming:
                    run_pass(only_pending=False)
                    upcoming = next_slot(datetime.now(timezone.utc), slots)
                else:
                    run_pass(only_pending=True)
        except Exception:  # keep the worker alive whatever goes wrong in one pass
            log.exception("loudness pass failed")
        (sleep or stop.wait)(poll)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from . import create_app

    app = create_app()
    stop = threading.Event()
    for name in ("SIGTERM", "SIGINT"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: stop.set())
    run_forever(app, stop)


if __name__ == "__main__":
    main()
