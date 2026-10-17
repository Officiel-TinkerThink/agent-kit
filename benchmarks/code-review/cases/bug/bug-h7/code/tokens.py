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
    expires_at: str = ""


def naive_utc_now() -> datetime:
    """Return the current time as a naive datetime in UTC for internal timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_token(subject: str, expires_at: str = "") -> Token:
    """Create a token for subject, stamped with the current UTC time."""
    now = naive_utc_now()
    token = Token(
        token_id=secrets.token_urlsafe(32),
        subject=subject,
        issued_at=now,
        last_seen=now,
        expires_at=expires_at,
    )
    logger.debug("token created subject=%s", subject)
    return token


def is_idle_expired(token: Token, idle_timeout, now=None) -> bool:
    """Return True when the token has been idle for longer than idle_timeout."""
    if now is None:
        now = naive_utc_now()
    return now - token.last_seen > idle_timeout


def is_expired(token: Token, now: datetime) -> bool:
    """Return True when the identity-provider expiry instant has passed.

    Expiry instants are ISO-8601 timestamps in UTC. now is a naive UTC datetime
    from naive_utc_now().
    """
    expires_at = datetime.fromisoformat(token.expires_at).replace(tzinfo=None)
    return now >= expires_at


def seconds_until(expires_at: datetime, now: datetime) -> int:
    """Return whole seconds from now until expires_at. Both arguments must be timezone-aware."""
    delta = expires_at.astimezone(timezone.utc) - now.astimezone(timezone.utc)
    return int(delta.total_seconds())
