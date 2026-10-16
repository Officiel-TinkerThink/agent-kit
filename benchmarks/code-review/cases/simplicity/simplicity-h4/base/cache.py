"""Region list access for the lab consumable pricing service."""

import functools
import logging

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
