"""Runtime settings for the lab profile service.

Values are read at import time. The only environment override is the
service token; every other setting is part of the released configuration
and changes only through a controlled release.
"""

import logging
import os

log = logging.getLogger("profiles.config")

SERVICE_NAME = "lab-profile-svc"
SERVICE_VERSION = "2.4.1"

# Profile names are written into the audit export as path segments, so the
# characters below are never accepted in a canonical name.
BANNED_NAME_CHARS = "/\\<>"
MAX_NAME_LENGTH = 64

# Hosts the URL importer may contact. The scheme is always https.
ALLOWED_IMPORT_HOSTS = frozenset(
    {
        "profiles.lab.example.test",
        "exports.lab.example.test",
    }
)
IMPORT_TIMEOUT_SECONDS = 10
MAX_IMPORT_BYTES = 262144
MAX_IMPORT_ROWS = 500

SESSION_TOKEN_HEADER = "X-Session-Token"
SERVICE_TOKEN_ENV = "PROFILE_SVC_TOKEN"

PAGE_SIZE_DEFAULT = 25
PAGE_SIZE_MAX = 100

LOG_LEVEL = os.environ.get("PROFILE_SVC_LOG_LEVEL", "INFO")


def load_service_token() -> str:
    """Return the configured service token, or an empty string when unset."""
    token = os.environ.get(SERVICE_TOKEN_ENV, "")
    if not token:
        log.error("service token is not configured")
    return token


def page_size(requested: int) -> int:
    """Clamp a requested page size to the supported range."""
    if requested <= 0:
        return PAGE_SIZE_DEFAULT
    return min(requested, PAGE_SIZE_MAX)


def import_limits() -> dict:
    """Return the import limits as a dictionary for the health report."""
    return {
        "timeout_seconds": IMPORT_TIMEOUT_SECONDS,
        "max_bytes": MAX_IMPORT_BYTES,
        "max_rows": MAX_IMPORT_ROWS,
        "hosts": sorted(ALLOWED_IMPORT_HOSTS),
    }


def service_info() -> dict:
    """Return the service name and version for the status endpoint."""
    return {"service": SERVICE_NAME, "version": SERVICE_VERSION}
