"""Release version parsing and precedence ordering.

Accepted layout: MAJOR.MINOR.PATCH[+BUILD]. Build metadata is kept for
display and never takes part in precedence.
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple

_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:\+([0-9A-Za-z.-]+))?$"
)


class VersionError(ValueError):
    """Raised when a version string does not follow the supported layout."""


@dataclass(frozen=True)
class Version:
    """A parsed release version that keeps its original text."""

    raw: str
    build: Optional[str]

    @property
    def core(self) -> str:
        """Return the MAJOR.MINOR.PATCH part of the version."""
        return self.raw.split("+", 1)[0]

    def precedence_key(self) -> Tuple:
        """Return a tuple whose natural ordering follows version precedence."""
        return tuple(int(part) for part in self.core.split("."))


def parse_version(text: str) -> Version:
    """Parse a version string, raising VersionError when it is unsupported."""
    if not isinstance(text, str):
        raise VersionError(f"version must be a string, got {type(text).__name__}")
    stripped = text.strip()
    match = _VERSION_PATTERN.match(stripped)
    if match is None:
        raise VersionError(f"unsupported version: {text!r}")
    return Version(raw=stripped, build=match.group(4))


def compare_versions(left: str, right: str) -> int:
    """Return -1, 0 or 1 when left is lower than, equal to or higher than right."""
    left_key = parse_version(left).precedence_key()
    right_key = parse_version(right).precedence_key()
    if left_key < right_key:
        return -1
    if left_key > right_key:
        return 1
    return 0
