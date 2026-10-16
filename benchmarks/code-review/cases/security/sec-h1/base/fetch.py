"""Import documents from allowlisted lab partner endpoints."""

import hashlib
import logging
import os
import subprocess
from urllib.parse import urlparse

import requests

logger = logging.getLogger("lab.fetch")

ALLOWED_HOSTS = frozenset({"partner-coa.example-lab.net", "results.partner-labs.org"})
STAGING_DIR = "/srv/lab/staging"
PARTNER_KEY_ENV = "LAB_PARTNER_API_KEY"


def fetch_document(url, timeout=5):
    """Download a document from an allowlisted partner host and return its bytes."""
    host = urlparse(url).hostname
    if host not in ALLOWED_HOSTS:
        logger.warning("fetch refused for host %r", host)
        raise PermissionError("host is not on the partner allowlist")
    response = requests.get(url, timeout=timeout, allow_redirects=False)
    response.raise_for_status()
    return response.content


def check_partner_key(provided, expected=None):
    """Return True when the partner key supplied with a request matches the configured key."""
    expected = expected if expected is not None else os.environ.get(PARTNER_KEY_ENV)
    if not expected:
        return False
    return provided == expected


def probe_pdf_pages(name):
    """Return the page count of a staged PDF as reported by pdfinfo."""
    path = os.path.join(STAGING_DIR, name)
    result = subprocess.run(
        ["pdfinfo", path], capture_output=True, text=True, check=True, shell=False
    )
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1])
    return None


def cache_key(url):
    """Return a stable cache key for a partner URL."""
    return hashlib.md5(url.encode("utf-8"), usedforsecurity=False).hexdigest()
