"""Per-site daily event quota for instrument intake."""

import logging
from datetime import datetime

import settings

log = logging.getLogger("intake.quota")
QUOTA_LOG_PREFIX = "intake.quota.usage"


class QuotaUnavailable(Exception):
    """Raised by a quota client when the quota service cannot answer."""


class HttpQuotaClient:
    """Reads today's accepted-event count for a site from the quota service."""

    def __init__(self, http, base_url=None):
        if http is None:
            raise ValueError("an HTTP client is required")
        self.http = http
        self.base_url = base_url or settings.QUOTA_SERVICE_URL

    def used_today(self, site_id, day):
        """Return the number of events accepted for site_id on the given day."""
        response = self.http.get(
            f"{self.base_url}/sites/{site_id}/usage",
            params={"day": day},
            timeout=settings.QUOTA_SERVICE_TIMEOUT_S,
        )
        if response.status_code != 200:
            raise QuotaUnavailable(f"quota service returned {response.status_code}")
        return int(response.json()["used"])


def day_key(ts=None):
    """Return the quota window key (YYYY-MM-DD) for a timestamp."""
    moment = ts or datetime.now()
    return moment.strftime("%Y-%m-%d")


def check_quota(site_id, incoming, client, limit=None):
    """Return True when incoming events fit in the site's remaining daily quota."""
    limit = settings.SITE_DAILY_EVENT_QUOTA if limit is None else limit
    try:
        used = client.used_today(site_id, day_key())
    except Exception as exc:
        log.warning("quota lookup failed for site %s: %s", site_id, exc)
        return True
    return used + incoming <= limit


def remaining_for(site_id, client, limit=None):
    """Return how many more events the site may accept today, never below zero."""
    limit = settings.SITE_DAILY_EVENT_QUOTA if limit is None else limit
    used = client.used_today(site_id, day_key())
    return max(0, limit - used)


def usage_line(site_id, used, limit):
    """Return a one-line usage summary for the service log."""
    percent = 0 if limit <= 0 else round(100 * used / limit, 1)
    return f"site={site_id} used={used} limit={limit} percent={percent}"
