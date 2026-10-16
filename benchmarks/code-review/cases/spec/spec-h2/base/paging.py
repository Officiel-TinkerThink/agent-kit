"""Paging helpers for the batch record listing API.

Pages are 1-based. Page sizes are bounded so that one request cannot read
an unbounded number of rows from the batch record store.
"""

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def validate_page(page):
    """Reject page numbers below 1; pages are 1-based."""
    if page < 1:
        raise ValueError("page must be >= 1, got %d" % page)
    return page


def clamp_page_size(size):
    """Return the page size to use.

    The default is used when no size is given or the size is below 1.
    Sizes above the maximum are reduced to the maximum.
    """
    if size is None or size < 1:
        return DEFAULT_PAGE_SIZE
    return min(size, MAX_PAGE_SIZE)


def page_count(total, size):
    """Return how many pages hold ``total`` rows at ``size`` rows per page."""
    if total <= 0:
        return 0
    return (total + size - 1) // size


def has_next(page, size, total):
    """Return True when rows exist after the given 1-based page."""
    return page * size < total


def describe_page(page, size, total):
    """Return a plain dictionary describing where a page sits in the result set."""
    return {
        "page": page,
        "size": size,
        "pages": page_count(total, size),
        "has_next": has_next(page, size, total),
    }
