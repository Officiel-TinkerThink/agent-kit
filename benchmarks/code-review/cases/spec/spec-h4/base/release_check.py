"""Release gate checks built on version precedence.

The gate decides whether a candidate release may be published for a
component, given the entries already present in the manifest.
"""

from typing import Iterable, Optional

from manifest import ReleaseEntry
from versions import compare_versions, parse_version


class ReleaseCheckError(RuntimeError):
    """Raised when a candidate release fails a gate."""


def latest_entry(entries: Iterable[ReleaseEntry]) -> Optional[ReleaseEntry]:
    """Return the entry with the highest version precedence, if any."""
    latest = None
    for entry in entries:
        if latest is None or compare_versions(entry.version, latest.version) > 0:
            latest = entry
    return latest


def is_major_bump(previous: str, candidate: str) -> bool:
    """Return True when the candidate raises the MAJOR component."""
    previous_major = int(parse_version(previous).core.split(".")[0])
    candidate_major = int(parse_version(candidate).core.split(".")[0])
    return candidate_major > previous_major


def describe_change(previous: str, candidate: str) -> str:
    """Return a short label for the kind of change between two versions."""
    if is_major_bump(previous, candidate):
        return "major"
    previous_minor = int(parse_version(previous).core.split(".")[1])
    candidate_minor = int(parse_version(candidate).core.split(".")[1])
    return "minor" if candidate_minor > previous_minor else "patch"
