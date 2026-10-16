"""Retry helper for lims gateway calls."""

import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger("lims.retry")

T = TypeVar("T")


class TransientError(Exception):
    """Raised by gateway clients for failures that may succeed on retry."""


def retry_call(operation: Callable[[], T], attempts: int = 3, delay_s: float = 0.5) -> T:
    """Call `operation` up to `attempts` times with a fixed pause between tries."""
    last_error: Exception = RuntimeError("no attempt was made")
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except TransientError as exc:
            last_error = exc
            logger.warning("attempt %d/%d failed: %s", attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(delay_s)
    raise last_error
