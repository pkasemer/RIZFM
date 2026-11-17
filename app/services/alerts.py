"""Team alerts for stream health.

Every alert is written to the log. If `HEALTH_ALERT_WEBHOOK_URL` is set it is also posted there as
JSON, so it can go to a chat channel: the body has both `text` (Slack, Mattermost, Teams connectors)
and `content` (Discord), plus `event` and `stationId` for anything custom.

Alerts are only sent when a station changes state (goes offline, recovers) and as a daily reminder
while it stays offline, never once per failed probe.
"""

import logging
import os

import requests

log = logging.getLogger("health")


def notify(event, station, message):
    """event is one of: offline, recovered, still_offline."""
    log.warning("ALERT %s %s: %s", event, station.id, message)
    url = os.getenv("HEALTH_ALERT_WEBHOOK_URL", "").strip()
    if not url:
        return
    try:
        requests.post(
            url,
            json={"text": message, "content": message, "event": event, "stationId": station.id},
            timeout=5,
        )
    except requests.RequestException:
        # A broken chat integration must never break health checking.
        log.exception("could not deliver the %s alert for %s", event, station.id)
