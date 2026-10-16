"""Runtime settings for the lab results sync service."""

import os
from dataclasses import dataclass

# Records sent to the lab gateway in one request.
MAX_BATCH_SIZE = 500

# Attempts per batch before it is parked for manual review.
MAX_RETRY_ATTEMPTS = 5

# Gateway request timeout, in milliseconds.
UPLOAD_TIMEOUT_MS = 30000

# Base delay between retries, in seconds; doubled on each attempt.
RETRY_BASE_DELAY_S = 2.0

# Upper bound for a single retry delay, in seconds.
MAX_BACKOFF_S = 60.0

GATEWAY_URL_ENV = "LAB_GATEWAY_URL"
GATEWAY_TOKEN_ENV = "LAB_GATEWAY_TOKEN"


@dataclass(frozen=True)
class SyncSettings:
    """Validated, immutable settings passed to the client and uploader."""

    gateway_url: str
    gateway_token: str
    batch_size: int = MAX_BATCH_SIZE
    retry_attempts: int = MAX_RETRY_ATTEMPTS
    timeout_ms: int = UPLOAD_TIMEOUT_MS

    @classmethod
    def from_environment(cls) -> "SyncSettings":
        url = os.environ.get(GATEWAY_URL_ENV, "").strip()
        token = os.environ.get(GATEWAY_TOKEN_ENV, "").strip()
        if not url.startswith("https://"):
            raise RuntimeError(f"{GATEWAY_URL_ENV} must be an https URL")
        if not token:
            raise RuntimeError(f"{GATEWAY_TOKEN_ENV} is not set")
        return cls(gateway_url=url, gateway_token=token)

    def validate(self) -> None:
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if self.retry_attempts < 1:
            raise ValueError("retry_attempts must be at least 1")
        if self.timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
