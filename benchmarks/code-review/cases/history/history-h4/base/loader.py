"""Loads peak feature files written by producer.py for search and export."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from feature_model import Feature, FeatureFormatError, has_unique_ids

log = logging.getLogger(__name__)

MAX_FEATURES = 60
SUPPORTED_FORMAT_VERSIONS = frozenset({2})


class FeatureFileError(ValueError):
    """Raised when a feature file cannot be accepted by the loader."""


def _read_document(path: Path) -> dict:
    """Parse the JSON document, rejecting anything that is not an object."""
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise FeatureFileError(f"{path.name}: top-level value must be an object")
    return document


def _check_version(document: dict, path: Path) -> None:
    """Reject files whose format_version the loader does not understand."""
    version = document.get("format_version")
    if version not in SUPPORTED_FORMAT_VERSIONS:
        raise FeatureFileError(f"{path.name}: unsupported format_version {version!r}")


def load_feature_file(path: Path) -> list[Feature]:
    """Return the features stored in one feature file.

    Raises FeatureFileError for an unreadable document, an unsupported format
    version, more entries than MAX_FEATURES, or duplicate feature ids.
    """
    document = _read_document(path)
    _check_version(document, path)
    rows = document.get("features", [])
    if not isinstance(rows, list):
        raise FeatureFileError(f"{path.name}: features must be a list")
    if len(rows) > MAX_FEATURES:
        raise FeatureFileError(f"{path.name}: {len(rows)} features exceeds limit {MAX_FEATURES}")
    try:
        features = [Feature.from_mapping(row) for row in rows]
    except FeatureFormatError as exc:
        raise FeatureFileError(f"{path.name}: {exc}") from exc
    if not has_unique_ids(features):
        raise FeatureFileError(f"{path.name}: duplicate feature_id values")
    log.info("loaded %d features from %s", len(features), path.name)
    return features


def load_directory(directory: Path) -> dict[str, list[Feature]]:
    """Load every feature file in a directory, keyed by file name.

    A file that fails validation is logged and skipped so that one rejected
    file does not block the rest of the batch.
    """
    loaded: dict[str, list[Feature]] = {}
    for path in sorted(directory.glob("*.features.json")):
        try:
            loaded[path.name] = load_feature_file(path)
        except FeatureFileError as exc:
            log.error("skipping feature file: %s", exc)
    return loaded


def count_rejected(directory: Path) -> int:
    """Return how many feature files in a directory fail validation."""
    rejected = 0
    for path in sorted(directory.glob("*.features.json")):
        try:
            load_feature_file(path)
        except FeatureFileError:
            rejected += 1
    return rejected
