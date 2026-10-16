"""Small list helpers shared by the lot, sample and batch modules."""

import logging
from typing import Callable, Dict, Iterable, List, Optional, Sequence, TypeVar

logger = logging.getLogger("lims.copy_utils")

T = TypeVar("T")


def snapshot_items(items: Iterable[T]) -> List[T]:
    """Return an independent list copy, so later caller mutations do not reach stored history."""
    return list(items)


def chunk(items: Sequence[T], size: int) -> List[List[T]]:
    """Split `items` into consecutive groups of at most `size` elements, preserving order."""
    groups: List[List[T]] = []
    for start in range(0, len(items), size):
        groups.append(list(items[start:start + size]))
    return groups


def dedupe_preserve_order(values: Iterable[T]) -> List[T]:
    """Drop repeated values, keeping the first occurrence of each."""
    seen = set()
    unique: List[T] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def first_or_none(values: Sequence[T]) -> Optional[T]:
    """Return the first element, or None when the sequence is empty."""
    return values[0] if values else None


def count_values(values: Iterable[T]) -> Dict[T, int]:
    """Count occurrences of each value, in first-seen order."""
    counts: Dict[T, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def join_codes(codes: Iterable[str], separator: str = ", ") -> str:
    """Join lot or sample codes for log lines and audit text, sorted; empty input gives an empty string."""
    return separator.join(sorted(str(code) for code in codes))


def group_by(items: Iterable[T], key: Callable[[T], str]) -> Dict[str, List[T]]:
    """Group items by the string returned from `key`, keeping input order inside each group.

    Callers are expected to return a str from key; other types are not converted.
    """
    groups: Dict[str, List[T]] = {}
    for item in items:
        groups.setdefault(key(item), []).append(item)
    return groups
