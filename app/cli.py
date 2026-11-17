"""Command line tools, run inside the API container:

    docker compose exec radio-api flask --app run loudness measure            # every active station
    docker compose exec radio-api flask --app run loudness measure --station kfm
    docker compose exec radio-api flask --app run loudness status
    docker compose exec radio-api flask --app run streams status                # stream health table
    docker compose exec radio-api flask --app run streams check --station kfm   # probe now
"""

import click
from flask.cli import AppGroup

from . import db
from .models import Station, iso_utc
from .services import loudness

loudness_cli = AppGroup("loudness", help="Station loudness measurement.")


@loudness_cli.command("measure")
@click.option("--station", "station_id", help="Only this station id (default: every active station).")
def measure(station_id):
    """Measure now, in the foreground, instead of waiting for the worker."""
    if station_id:
        station = db.session.get(Station, station_id)
        if station is None:
            raise click.ClickException(f"No station with id {station_id!r}")
        if not station.stream_url:
            raise click.ClickException(f"{station_id} has no stream URL")
        stations = [station]
    else:
        stations = loudness.measurable_stations()

    click.echo(f"Measuring {len(stations)} station(s), up to {loudness.MAX_PARALLEL} at a time...")
    results = loudness.measure_stations(stations)
    for station in stations:
        accepted = results.get(station.id)
        db.session.refresh(station)
        value = "-" if station.loudness_lufs is None else f"{station.loudness_lufs:.1f} LUFS"
        click.echo(f"  {station.id:<16} {'ok      ' if accepted else 'REJECTED'} published: {value}")


@loudness_cli.command("status")
def status():
    """Show what is published, and which stations need review."""
    stations = Station.query.order_by(Station.id).all()
    click.echo(f"{'station':<16} {'LUFS':>7}  {'measured at (UTC)':<26} {'fails':>5}  notes")
    for station in stations:
        notes = []
        if station.loudness_pending:
            notes.append("pending")
        if (station.loudness_fail_streak or 0) >= loudness.REVIEW_AFTER_FAILURES:
            notes.append("NEEDS REVIEW")
        if not station.is_active:
            notes.append("inactive")
        value = "-" if station.loudness_lufs is None else f"{station.loudness_lufs:.1f}"
        click.echo(
            f"{station.id:<16} {value:>7}  {iso_utc(station.loudness_measured_at) or '-':<26} "
            f"{station.loudness_fail_streak or 0:>5}  {', '.join(notes)}"
        )


# --- stream health ------------------------------------------------------------------------------

from .services import health  # noqa: E402

streams_cli = AppGroup("streams", help="Stream health checks.")


@streams_cli.command("check")
@click.option("--station", "station_id", help="Only this station id (default: every active station).")
def check(station_id):
    """Probe now, in the foreground, instead of waiting for the worker."""
    if station_id:
        station = db.session.get(Station, station_id)
        if station is None:
            raise click.ClickException(f"No station with id {station_id!r}")
        stations = [station]
    else:
        stations = Station.query.filter(Station.is_active.is_(True), Station.stream_url.isnot(None)).all()

    click.echo(f"Probing {len(stations)} station(s), up to {health.MAX_PARALLEL} at a time...")
    results = health.probe_stations([s for s in stations if s.stream_url])
    for station in stations:
        db.session.refresh(station)
        result = results.get(station.id)
        outcome = "pass" if result and result.ok else f"FAIL {result.error if result else 'no url'}"
        took = f"{result.response_ms} ms" if result and result.response_ms is not None else "-"
        click.echo(f"  {station.id:<16} {outcome:<22} {station.stream_status:<9} {took:>8}")


@streams_cli.command("status")
def streams_status():
    """The admin table: status, last online, last error, 30-day uptime."""
    click.echo(f"{'station':<16} {'status':<9} {'fails':>5} {'uptime30d':>9}  {'last online (UTC)':<26} {'last error':<16} notes")
    for row in health.health_table():
        uptime = "-" if row["uptime30d"] is None else f"{row['uptime30d']}%"
        notes = ", ".join(n for n, on in (("http only", row["httpOnly"]), ("inactive", not row["isActive"])) if on)
        click.echo(
            f"{row['id']:<16} {row['streamStatus']:<9} {row['consecutiveFailures']:>5} {uptime:>9}  "
            f"{row['lastOnlineAt'] or '-':<26} {row['lastError'] or '-':<16} {notes}"
        )
