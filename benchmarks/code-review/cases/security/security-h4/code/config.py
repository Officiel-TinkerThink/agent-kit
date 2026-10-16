"""Runtime settings for the lab reporting service."""

import os
from dataclasses import dataclass

REPORT_CACHE_ROOT = "/srv/labcache/reports"
REPORT_CONTENT_TYPE = "application/pdf"
DOWNLOAD_CHUNK_BYTES = 64 * 1024

ROLE_ANALYST = "analyst"
ROLE_ADMIN = "admin"
ROLES = (ROLE_ANALYST, ROLE_ADMIN)

PROFILE_FIELDS = ("display_name", "email")
USER_FIELDS = ("user_id", "display_name", "email", "role", "is_admin")

SESSION_TTL_SECONDS = 1800
MAX_PAYLOAD_BYTES = 16 * 1024
LIST_PAGE_SIZE = 50
ALLOWED_EXPORT_FORMATS = ("pdf", "csv")

DEFAULT_DB_PATH = "/var/lib/labrpt/labrpt.sqlite3"
DEFAULT_LOG_LEVEL = "INFO"
VALID_LOG_LEVELS = ("INFO", "WARNING", "ERROR")
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings resolved from the environment."""

    db_path: str
    log_level: str
    session_ttl: int

    @classmethod
    def from_env(cls, environ=None):
        """Build settings from environment variables, falling back to defaults."""
        env = os.environ if environ is None else environ
        return cls(
            db_path=env.get("LABRPT_DB_PATH", DEFAULT_DB_PATH),
            log_level=env.get("LABRPT_LOG_LEVEL", DEFAULT_LOG_LEVEL),
            session_ttl=int(env.get("LABRPT_SESSION_TTL", SESSION_TTL_SECONDS)),
        )

    def validate(self):
        """Raise ValueError when a setting cannot be used at start-up."""
        if self.session_ttl <= 0:
            raise ValueError("session_ttl must be positive")
        if self.log_level not in VALID_LOG_LEVELS:
            raise ValueError(f"unsupported log level {self.log_level!r}")
        if not self.db_path:
            raise ValueError("db_path must not be empty")
        return self

    def describe(self):
        """Return the settings as a plain dictionary for the start-up log line."""
        return {
            "db_path": self.db_path,
            "log_level": self.log_level,
            "session_ttl": self.session_ttl,
        }
