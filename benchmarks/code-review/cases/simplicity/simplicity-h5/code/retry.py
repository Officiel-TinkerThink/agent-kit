"""Bounded retry with exponential backoff and jitter for transient gateway errors.

The LIMS client and the batch-record gateway raise TransientError for timeouts,
HTTP 503 responses and connection resets. Other exceptions propagate on the first attempt.
"""

import logging
import random
import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, Type, TypeVar

logger = logging.getLogger("lims.retry")

T = TypeVar("T")


class TransientError(Exception):
    """Raised by gateway clients for failures that may succeed on retry."""


class RetriesExhausted(Exception):
    """Raised when every attempt failed with a retryable error."""

    def __init__(self, attempts: int, last_error: Optional[BaseException]) -> None:
        super().__init__(f"gave up after {attempts} attempts: {last_error}")
        self.attempts = attempts
        self.last_error = last_error


@dataclass(frozen=True)
class RetryPolicy:
    """Immutable retry settings shared by all gateway calls."""

    max_attempts: int = 4
    base_delay_s: float = 0.5
    max_delay_s: float = 8.0
    jitter_ratio: float = 0.2
    retry_on: Tuple[Type[BaseException], ...] = (TransientError,)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay_s < 0 or self.max_delay_s < self.base_delay_s:
            raise ValueError("delays must satisfy 0 <= base_delay_s <= max_delay_s")


def backoff_delay(policy: RetryPolicy, failed_attempt: int, rng: random.Random) -> float:
    """Return the sleep in seconds after attempt `failed_attempt` (1-based) failed.

    The delay doubles per attempt, is capped at max_delay_s, and then has up to
    jitter_ratio of its value removed at random so concurrent clients spread out.
    """
    exponential = policy.base_delay_s * (2 ** (failed_attempt - 1))
    capped = min(exponential, policy.max_delay_s)
    return capped * (1.0 - policy.jitter_ratio * rng.random())


def retry_call(
    operation: Callable[[], T],
    policy: RetryPolicy,
    *,
    operation_name: str,
    sleep: Callable[[float], None] = time.sleep,
    rng: Optional[random.Random] = None,
) -> T:
    """Invoke `operation` until it succeeds, raises a non-retryable error, or attempts run out."""
    generator = rng if rng is not None else random.Random()
    last_error: Optional[BaseException] = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation()
        except policy.retry_on as exc:
            last_error = exc
            logger.warning("%s attempt %d/%d failed: %s", operation_name, attempt, policy.max_attempts, exc)
            if attempt == policy.max_attempts:
                break
            sleep(backoff_delay(policy, attempt, generator))
    raise RetriesExhausted(policy.max_attempts, last_error)
