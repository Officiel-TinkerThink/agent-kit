"""In-memory session token store with idle expiry and a per-subject limit."""
import logging

from config import IDLE_TIMEOUT, MAX_TOKENS_PER_SUBJECT
from tokens import Token, is_idle_expired, naive_utc_now, new_token

logger = logging.getLogger(__name__)


class TokenStore:
    """Holds active tokens keyed by token_id. Not thread-safe; wrap with a lock if shared."""

    def __init__(self):
        self._tokens = {}

    def issue(self, subject: str) -> Token:
        if not subject:
            raise ValueError("subject must be a non-empty string")
        active = [t for t in self._tokens.values() if t.subject == subject]
        if len(active) >= MAX_TOKENS_PER_SUBJECT:
            oldest = min(active, key=lambda t: t.issued_at)
            del self._tokens[oldest.token_id]
            logger.info("evicted oldest token subject=%s", subject)
        token = new_token(subject)
        self._tokens[token.token_id] = token
        logger.info("token issued subject=%s", subject)
        return token

    def get(self, token_id: str):
        token = self._tokens.get(token_id)
        if token is None:
            return None
        if is_idle_expired(token, IDLE_TIMEOUT):
            del self._tokens[token_id]
            logger.info("token idle-expired subject=%s", token.subject)
            return None
        token.last_seen = naive_utc_now()
        return token
