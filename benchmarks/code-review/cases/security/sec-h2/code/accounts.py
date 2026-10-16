"""Account creation, retry and reset-code helpers for the lab portal."""

import random
import time
from dataclasses import dataclass

from validate import validate_display_name, validate_role, validate_username

MAX_RETRY_ATTEMPTS = 5
RETRY_CAP_SECONDS = 60.0


@dataclass
class Account:
    """Portal account record as stored in the lab user table."""

    username: str
    display_name: str
    role: str = "analyst"
    is_admin: bool = False


def account_from_request(payload):
    """Build an Account from a client request body, accepting only the fields the form sends."""
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    username = validate_username(payload.get("username"))
    display_name = validate_display_name(payload.get("display_name"))
    role = validate_role(payload.get("role", "analyst"))
    return Account(**{**payload, "username": username, "display_name": display_name, "role": role})


def audit_line(action, account):
    """Format one audit log entry for an account action."""
    return "{} user={} role={}".format(action, account.username, account.role)


def retry_delay(attempt):
    """Return the back-off delay in seconds for a retry attempt, with jitter."""
    base = min(RETRY_CAP_SECONDS, 2.0 ** attempt)
    return base + random.uniform(0.0, 1.0)


def wait_before_retry(attempt, sleep=time.sleep):
    """Sleep before a retry, refusing once the attempt limit is reached."""
    if attempt >= MAX_RETRY_ATTEMPTS:
        raise RuntimeError("retry limit reached")
    sleep(retry_delay(attempt))


def verify_reset_code(stored_code, supplied_code):
    """Return True when the supplied reset code matches the stored code."""
    if not stored_code or not supplied_code:
        return False
    return stored_code == supplied_code
