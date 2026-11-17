"""Kept so existing imports keep working. The real logic is in `services/health.py`."""

from . import health


def check_stream(station):
    """Probe one station now, record the result, and return True if its stream works."""
    return health.check_station(station).ok
