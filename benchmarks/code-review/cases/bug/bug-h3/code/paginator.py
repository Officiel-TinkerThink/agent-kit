"""Pagination helpers for listing samples in fixed-size windows."""

import logging
from typing import Callable, Iterator, List, Optional, Tuple

from models import Sample


logger = logging.getLogger("lab.paginator")

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000

Cursor = Optional[Tuple]
FetchAfter = Callable[[Cursor, int], List[Sample]]


def validate_page_size(page_size: int) -> int:
    """Return page_size if it is an integer within 1..MAX_PAGE_SIZE, otherwise raise ValueError."""
    if not isinstance(page_size, int) or isinstance(page_size, bool):
        raise ValueError("page_size must be an integer")
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    return page_size


def describe_window(offset: int, page_size: int) -> str:
    """Return a short label for the window that starts at offset."""
    validate_page_size(page_size)
    return f"rows {offset + 1}-{offset + page_size}"


def page_count(total: int, page_size: int) -> int:
    """Return how many pages hold total rows; zero rows need zero pages."""
    validate_page_size(page_size)
    if total < 0:
        raise ValueError("total must not be negative")
    return -(-total // page_size)


class KeysetPaginator:
    """Walks samples in (created_at, sample_id) order from the last key seen.

    fetch_after(cursor, limit) returns up to limit samples whose key is greater
    than cursor, or the first samples in order when cursor is None.
    """

    def __init__(self, fetch_after: FetchAfter, page_size: int) -> None:
        self._fetch_after = fetch_after
        self._page_size = validate_page_size(page_size)

    def pages(self) -> Iterator[List[Sample]]:
        """Yield pages until fetch_after returns an empty page."""
        cursor: Cursor = None
        while True:
            page = self._fetch_after(cursor, self._page_size)
            if not page:
                logger.info("keyset walk finished")
                return
            yield page
            last = page[-1]
            cursor = (last.created_at, last.sample_id)
            logger.info("keyset cursor advanced to %s", last.sample_id)
