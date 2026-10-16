"""Region list access and memoised tax computation for the lab consumable pricing service."""

import functools
import logging
import threading

from helpers import tax_on

logger = logging.getLogger("pricing.cache")

REGION_LIST_LIMIT = 200


@functools.lru_cache(maxsize=8)
def load_region_codes(path):
    """Return the configured region codes from a text file, one per line.

    The result is an immutable tuple, cached per path for the life of the process.
    The region file is written only during deployment, which restarts the process.
    """
    codes = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            code = line.strip()
            if code:
                codes.append(code)
    if len(codes) > REGION_LIST_LIMIT:
        logger.warning("region list longer than %d entries", REGION_LIST_LIMIT)
    return tuple(codes)


@functools.lru_cache(maxsize=512)
def _tax_cached(amount, region, generation):
    """Compute the tax for one amount and region; generation only partitions the cache."""
    return tax_on(amount, region)


class TaxMemo:
    """Memoises tax results; invalidate() moves later lookups to a new generation."""

    def __init__(self):
        """Create an empty memo at generation zero."""
        self._lock = threading.Lock()
        self._generation = 0

    def tax_for(self, amount, region):
        """Return the tax for an amount in a region, reusing cached results."""
        with self._lock:
            generation = self._generation
        return _tax_cached(amount, region, generation)

    def invalidate(self):
        """Start a new generation so that subsequent lookups recompute."""
        with self._lock:
            self._generation += 1
            logger.info("tax memo generation=%d", self._generation)
