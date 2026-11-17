"""Background job that keeps every station's stream health up to date.

Run it as its own process (the `health-worker` service in docker-compose.yml):

    python -m app.health_worker

Each station stores when it is next due (`health_next_check_at`), so a restart loses nothing:

  * healthy (online / degraded)        every 5 minutes
  * suspect (1 or 2 failures so far)   every 1 minute, until it passes or reaches 3 failures
  * confirmed offline                  every 15 minutes
  * new, or its stream URL just changed: as soon as possible (next tick), not on the next interval

At most 8 probes run at once. Each station also has a fixed 0-59 second offset so the checks are
spread out rather than all hitting at the same second.
"""

import logging
import os
import signal
import threading
import time

from .services import health

log = logging.getLogger("health")

DEFAULT_TICK_SECONDS = 5
PRUNE_EVERY_SECONDS = 3600


def run_due(now=None):
    """Probe every station that is due. Returns {station_id: ProbeResult}."""
    stations = health.checkable_stations(now=now)
    if not stations:
        return {}
    results = health.probe_stations(stations)
    failed = [station_id for station_id, result in results.items() if not result.ok]
    log.info("checked %d station(s), %d failed%s", len(results), len(failed),
             f": {', '.join(sorted(failed))}" if failed else "")
    return results


def run_forever(app, stop=None, tick_seconds=None, sleep=None, clock=time.monotonic):
    stop = stop or threading.Event()
    tick = tick_seconds if tick_seconds is not None else float(os.getenv("HEALTH_TICK_SECONDS", DEFAULT_TICK_SECONDS))
    log.info("health worker started; checking every %ss for stations that are due", tick)
    next_prune = clock()

    while not stop.is_set():
        try:
            with app.app_context():
                run_due()
                if clock() >= next_prune:
                    removed = health.prune_history()
                    next_prune = clock() + PRUNE_EVERY_SECONDS
                    if removed:
                        log.info("pruned %d old probe record(s)", removed)
        except Exception:  # keep the worker alive whatever goes wrong in one pass
            log.exception("health pass failed")
        (sleep or stop.wait)(tick)


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
