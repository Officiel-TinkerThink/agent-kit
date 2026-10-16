"""Ordering helpers for sample listings and exports."""

from functools import cmp_to_key
from typing import Iterable, List, Optional

from models import VALID_STATUSES, Sample


SORT_KEYS = ("collected", "score")


def sort_by_collected(samples: Iterable[Sample]) -> List[Sample]:
    """Return samples ordered by collection time, then sample_id."""
    return sorted(samples, key=lambda s: (s.created_at, s.sample_id))


def _compare_site(a: Sample, b: Sample) -> int:
    """Return -1, 0 or 1 for the site order of two samples."""
    return (a.site > b.site) - (a.site < b.site)


def sort_by_site(samples: Iterable[Sample]) -> List[Sample]:
    """Return samples ordered by site name, keeping collection order within a site."""
    return sorted(sort_by_collected(samples), key=cmp_to_key(_compare_site))


def sort_by_status(samples: Iterable[Sample]) -> List[Sample]:
    """Return samples in workflow status order, then sample_id."""
    rank = {status: index for index, status in enumerate(VALID_STATUSES)}
    return sorted(samples, key=lambda s: (rank[s.status], s.sample_id))


def is_collected_order(samples: List[Sample]) -> bool:
    """Return True when samples are already in collected order."""
    keys = [(s.created_at, s.sample_id) for s in samples]
    return all(a <= b for a, b in zip(keys, keys[1:]))


def _compare_score(a: Sample, b: Sample) -> int:
    """Return a negative, zero or positive value for ascending score order."""
    return int(a.score - b.score)


def sort_by_score(samples: Iterable[Sample]) -> List[Sample]:
    """Return samples ordered by ascending assay score."""
    return sorted(samples, key=cmp_to_key(_compare_score))


def lowest_score(samples: Iterable[Sample]) -> Optional[Sample]:
    """Return the sample with the lowest assay score, or None when there are no samples."""
    ordered = sort_by_score(samples)
    return ordered[0] if ordered else None


def sort_samples(samples: Iterable[Sample], by: str) -> List[Sample]:
    """Dispatch to the ordering named by `by`; unknown names raise ValueError."""
    if by == "collected":
        return sort_by_collected(samples)
    if by == "score":
        return sort_by_score(samples)
    raise ValueError(f"unknown sort key {by!r}; expected one of {SORT_KEYS}")
