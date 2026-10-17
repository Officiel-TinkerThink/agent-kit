"""Email address validation shared by every entry point."""

from __future__ import annotations

import re

MAX_EMAIL_LENGTH = 254
_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")


def valid_email(address: object) -> bool:
    """Return True when address is a syntactically valid email address."""
    if not isinstance(address, str):
        return False
    if len(address) > MAX_EMAIL_LENGTH:
        return False
    return _EMAIL_PATTERN.match(address) is not None
