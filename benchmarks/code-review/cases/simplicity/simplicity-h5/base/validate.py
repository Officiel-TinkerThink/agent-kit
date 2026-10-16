"""Input validation for lot capture forms."""

import re
from typing import Optional

LOT_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{4,10}[A-Z0-9]$")
MAX_QUANTITY_UNITS = 10_000


class ValidationError(ValueError):
    """Raised when a submitted field fails validation; the message names the field."""


def effective_quantity(submitted: Optional[int], batch_default: int) -> int:
    """Resolve the quantity to store for a capture form."""
    return submitted or batch_default


def parse_lot_code(raw: str) -> str:
    """Normalise and validate a lot code: letters, digits and hyphens, 6 to 12 characters."""
    if not isinstance(raw, str):
        raise ValidationError("lot code must be a string")
    candidate = raw.strip().upper()
    if not LOT_CODE_PATTERN.fullmatch(candidate):
        raise ValidationError(f"invalid lot code: {raw!r}")
    return candidate


def parse_optional_text(raw: Optional[str]) -> Optional[str]:
    """Return the stripped text, or None when the field is blank or absent.

    Used for optional free-text fields on capture forms, such as the reviewer note.
    """
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None
