"""Display-name and lookup-key handling for lab operator profiles."""

import logging
import unicodedata

from config import BANNED_NAME_CHARS, MAX_NAME_LENGTH

log = logging.getLogger("profiles.names")


class ProfileNameError(ValueError):
    """Raised when a profile name cannot be accepted."""


def _canonical(name: str) -> str:
    """Return the NFKC form of a name with surrounding whitespace removed."""
    return unicodedata.normalize("NFKC", name).strip()


def normalise_for_lookup(name: str) -> str:
    """Return the lookup key for a profile name, case-folded."""
    if not isinstance(name, str):
        raise ProfileNameError("name must be a string")
    canonical = _canonical(name)
    if any(ch in BANNED_NAME_CHARS for ch in canonical):
        raise ProfileNameError("name contains a reserved character")
    if not canonical or len(canonical) > MAX_NAME_LENGTH:
        raise ProfileNameError("name length out of range")
    return canonical.casefold()


def display_name(name: str) -> str:
    """Return the display form of a name with internal runs of whitespace collapsed."""
    if not isinstance(name, str):
        raise ProfileNameError("name must be a string")
    return " ".join(name.split())


def is_reserved(name: str) -> bool:
    """Return True when the name cannot be used as a profile key."""
    try:
        normalise_for_lookup(name)
    except ProfileNameError:
        return True
    return False


def same_profile(left: str, right: str) -> bool:
    """Return True when two names resolve to the same lookup key."""
    try:
        return normalise_for_lookup(left) == normalise_for_lookup(right)
    except ProfileNameError:
        return False


def export_key(name: str) -> str:
    """Return the key written into the audit export for a stored name."""
    return normalise_for_lookup(name).replace(" ", "_")


def length_within_limit(name: str) -> bool:
    """Return True when the canonical form fits the configured name length."""
    return 0 < len(_canonical(name)) <= MAX_NAME_LENGTH
