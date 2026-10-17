"""Idempotency store for payment requests.

Results are kept in process memory, keyed by the client-supplied idempotency key.
"""

import logging
import threading

logger = logging.getLogger("payments.idempotency")

_results = {}
_lock = threading.Lock()


def remember_result(key, result):
    """Store result under key unless one is already stored; return the stored value."""
    with _lock:
        if key in _results:
            logger.info("idempotency hit key=%s", key)
            return _results[key]
        _results[key] = result
        return result


def clear():
    """Remove all stored results. Intended for test isolation."""
    with _lock:
        _results.clear()
