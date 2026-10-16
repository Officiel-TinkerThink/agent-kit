"""Retry helpers for outbound service calls."""

from __future__ import annotations

import functools
import logging
import random
import time
from typing import Any, Callable, Optional, TypeVar

from models import PaymentError

LOGGER = logging.getLogger("orders.retry")

F = TypeVar("F", bound=Callable[..., Any])


def validate_policy(max_attempts: int, base_s: float, cap_s: float) -> None:
    """Reject retry policies that cannot produce a valid schedule."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if base_s <= 0 or cap_s < base_s:
        raise ValueError("require 0 < base_s <= cap_s")


def full_jitter_delay(
    attempt: int,
    base_s: float = 0.2,
    cap_s: float = 5.0,
    rng: Optional[random.Random] = None,
) -> float:
    """Return the sleep before retry number ``attempt`` (1-based), in seconds.

    The delay is drawn uniformly from [0, min(cap_s, base_s * 2**(attempt - 1))].
    """
    validate_policy(1, base_s, cap_s)
    if attempt < 1:
        raise ValueError("attempt is 1-based")
    ceiling = min(cap_s, base_s * (2 ** (attempt - 1)))
    generator = rng if rng is not None else random
    return generator.uniform(0.0, ceiling)


def retry_call(max_attempts: int = 3) -> Callable[[F], F]:
    """Decorate a callable so that a failed call is retried up to ``max_attempts`` times.

    Each failed attempt is logged with its number. When every attempt has failed,
    PaymentError is raised.
    """
    validate_policy(max_attempts, 0.5, 0.5)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    LOGGER.warning(
                        "%s failed on attempt %d of %d", func.__name__, attempt, max_attempts
                    )
                    time.sleep(0.5 * attempt)
            raise PaymentError(f"{func.__name__} failed after {max_attempts} attempts")

        return wrapper  # type: ignore[return-value]

    return decorator
