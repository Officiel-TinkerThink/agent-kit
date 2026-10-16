"""Release manifest loading, validation and writing.

A manifest is a JSON document with an "entries" list. Each entry names a
component, its version and the RFC 3339 time of release.
"""

import json
from dataclasses import dataclass
from typing import List

from timestamps import TimestampError, format_timestamp, parse_timestamp
from versions import VersionError, parse_version

REQUIRED_FIELDS = ("component", "version", "released_at")


class ManifestError(ValueError):
    """Raised when a manifest is missing data or contains invalid values."""


@dataclass(frozen=True)
class ReleaseEntry:
    """One released component version."""

    component: str
    version: str
    released_at: str


def load_manifest(path: str) -> List[ReleaseEntry]:
    """Load and validate a manifest file, returning entries in file order."""
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    items = document.get("entries") if isinstance(document, dict) else None
    if not isinstance(items, list):
        raise ManifestError("manifest must contain an 'entries' list")
    return [_entry_from_dict(item, index) for index, item in enumerate(items)]


def _entry_from_dict(item: dict, index: int) -> ReleaseEntry:
    if not isinstance(item, dict):
        raise ManifestError(f"entry {index} must be an object")
    missing = [name for name in REQUIRED_FIELDS if name not in item]
    if missing:
        raise ManifestError(f"entry {index} is missing {', '.join(missing)}")
    try:
        parse_version(item["version"])
        parse_timestamp(item["released_at"])
    except (VersionError, TimestampError) as exc:
        raise ManifestError(f"entry {index} is invalid: {exc}") from exc
    return ReleaseEntry(
        component=str(item["component"]),
        version=item["version"],
        released_at=item["released_at"],
    )


def write_manifest(entries: List[ReleaseEntry], path: str) -> None:
    """Write entries as a manifest with canonical UTC timestamps."""
    payload = {
        "entries": [
            {
                "component": entry.component,
                "version": entry.version,
                "released_at": format_timestamp(parse_timestamp(entry.released_at)),
            }
            for entry in entries
        ]
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
