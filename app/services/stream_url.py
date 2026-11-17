"""Which stream URLs the server is willing to open.

Anyone can set a station's stream URL through the API, and the loudness and health jobs then connect
to it from inside the server. So only public http(s) hosts are allowed: a station must not be able to
make the server fetch localhost, 10.x, 169.254.x (cloud metadata) and so on.
"""

import ipaddress
import os
import socket
from urllib.parse import urlparse


def _private_hosts_allowed():
    # Development and tests only (a stream served from localhost).
    for name in ("ALLOW_PRIVATE_STREAM_HOSTS", "LOUDNESS_ALLOW_PRIVATE_HOSTS"):
        if os.getenv(name, "").lower() in ("1", "true", "yes"):
            return True
    return False


def check_stream_url(url):
    """(ok, reason). Only public http(s) hosts pass."""
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False, "stream URL is not http(s)"
    if _private_hosts_allowed():
        return True, None
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80),
                                   type=socket.SOCK_STREAM)
    except OSError:
        return False, "host could not be resolved"
    for info in infos:
        try:
            address = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False, "host resolved to an unreadable address"
        if not address.is_global:
            return False, "host resolves to a non-public address"
    return True, None
