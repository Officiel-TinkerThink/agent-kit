"""Token model and idle-expiry checks for the session token store."""
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class Token:
    """A session token. The token_id is a secret and must never be logged."""

    token_id: str
    subject: str
    issued_at: datetime
    last_seen: datetime


def naive_utc_now() -> datetime:
    """Return the current time as a naive datetime in UTC for internal timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_token(subject: str) -> Token:
    """Create a token for subject, stamped with the current UTC time."""
    now = naive_utc_now()
    token = Token(
        token_id=secrets.token_urlsafe(32),
        subject=subject,
        issued_at=now,
        last_seen=now,
    )
    logger.debug("token created subject=%s", subject)
    return token


def is_idle_expired(token: Token, idle_timeout, now=None) -> bool:
    """Return True when the token has been idle for longer than idle_timeout."""
    if now is None:
        now = naive_utc_now()
    return now - token.last_seen > idle_timeout
