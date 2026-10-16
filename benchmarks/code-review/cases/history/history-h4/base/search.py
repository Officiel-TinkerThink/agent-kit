"""Name and pattern search over peak features for the review screen."""

from __future__ import annotations

import logging
import re
from typing import Iterable

from feature_model import Feature

log = logging.getLogger(__name__)

MAX_PATTERN_CHARS = 256
DEFAULT_FLAGS = re.IGNORECASE


class PatternError(ValueError):
    """Raised when a search pattern is rejected before it is compiled."""


def _check_pattern_length(pattern: str) -> None:
    """Reject patterns longer than MAX_PATTERN_CHARS before any regex work."""
    if len(pattern) > MAX_PATTERN_CHARS:
        raise PatternError(
            f"pattern length {len(pattern)} exceeds {MAX_PATTERN_CHARS} characters"
        )


def _compile(pattern: str) -> re.Pattern:
    """Compile a user pattern, translating regex errors into PatternError."""
    if not pattern:
        raise PatternError("pattern must not be empty")
    try:
        return re.compile(pattern, DEFAULT_FLAGS)
    except re.error as exc:
        raise PatternError(f"invalid pattern: {exc}") from exc


def filter_features(features: Iterable[Feature], pattern: str) -> list[Feature]:
    """Return features whose name matches the regular expression pattern.

    Matching is a search (not a full match) and is case-insensitive.
    """
    _check_pattern_length(pattern)
    compiled = _compile(pattern)
    matched = [feature for feature in features if compiled.search(feature.name)]
    log.info("pattern matched %d features", len(matched))
    return matched


def find_by_id(features: Iterable[Feature], feature_id: str) -> Feature | None:
    """Return the feature with the given id, or None when absent."""
    for feature in features:
        if feature.feature_id == feature_id:
            return feature
    return None


def retention_window(features: Iterable[Feature], low: float, high: float) -> list[Feature]:
    """Return features whose retention time lies in the closed interval [low, high]."""
    if low > high:
        raise ValueError("low must not exceed high")
    return [feature for feature in features if low <= feature.retention_time <= high]
