"""Outbound snapshot fetch for profile imports.

The lab HTTP transport is bound at deploy time. _transport_get below is the
call-site contract only.
"""

import logging
from urllib.parse import urlparse

from config import ALLOWED_IMPORT_HOSTS, IMPORT_TIMEOUT_SECONDS, MAX_IMPORT_BYTES

log = logging.getLogger("profiles.fetcher")


class FetchError(RuntimeError):
    """Raised when a remote snapshot cannot be retrieved."""


def _transport_get(host: str, path: str, timeout: int, max_bytes: int) -> bytes:
    """Contract stub for the lab HTTP client; returns the response body."""
    raise NotImplementedError("transport is bound at deploy time")


def _check_scheme_and_host(url: str) -> None:
    """Raise FetchError unless the URL uses https and an allow-listed host."""
    parts = urlparse(url)
    if parts.scheme != "https":
        raise FetchError("only https sources are allowed")
    if parts.hostname not in ALLOWED_IMPORT_HOSTS:
        raise FetchError("source host is not on the import allow-list")


def _redact(url: str) -> str:
    """Return the scheme and host of a URL for logging, without path or query."""
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.hostname}"


def fetch_snapshot(url: str) -> bytes:
    """Fetch a profile snapshot from an allow-listed https host."""
    _check_scheme_and_host(url)
    parts = urlparse(url)
    log.info("fetching snapshot from %s", _redact(url))
    body = _transport_get(
        parts.hostname,
        parts.path or "/",
        IMPORT_TIMEOUT_SECONDS,
        MAX_IMPORT_BYTES,
    )
    if len(body) > MAX_IMPORT_BYTES:
        raise FetchError("snapshot exceeds size limit")
    return body


def _split_target(url: str):
    """Split an https URL into the (host, path) pair sent to the transport."""
    rest = url[len("https://"):]
    cut = len(rest)
    for sep in "/?#\\":
        idx = rest.find(sep)
        if 0 <= idx < cut:
            cut = idx
    authority, path = rest[:cut], rest[cut:] or "/"
    host = authority.rsplit("@", 1)[-1].split(":", 1)[0].lower()
    return host, path


def import_profile_from_url(url: str) -> bytes:
    """Fetch a profile export from an allow-listed https URL."""
    _check_scheme_and_host(url)
    host, path = _split_target(url)
    log.info("importing profile export from %s", host)
    body = _transport_get(host, path, IMPORT_TIMEOUT_SECONDS, MAX_IMPORT_BYTES)
    if len(body) > MAX_IMPORT_BYTES:
        raise FetchError("export exceeds size limit")
    return body
