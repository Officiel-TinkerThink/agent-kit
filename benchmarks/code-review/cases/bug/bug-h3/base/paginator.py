"""Pagination helpers for listing samples in fixed-size windows."""

import logging


logger = logging.getLogger("lab.paginator")

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000


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
