"""Input validation for lot and sample capture forms.

Lot codes are normalised to upper case. Sample codes are case-sensitive and must already
be lower case. A quantity field distinguishes an untouched field (None) from an explicit zero.
"""

import re
from typing import Optional

LOT_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{4,10}[A-Z0-9]$")
SAMPLE_CODE_PATTERN = re.compile(r"^[a-z0-9]{8}$")
MAX_QUANTITY_UNITS = 10_000


class ValidationError(ValueError):
    """Raised when a submitted field fails validation; the message names the field."""


def effective_quantity(submitted: Optional[int], batch_default: int) -> int:
    """Resolve the quantity to store: None takes the batch default, an explicit 0 is kept."""
    if batch_default < 0:
        raise ValidationError("batch_default must not be negative")
    if submitted is None:
        return batch_default
    if isinstance(submitted, bool) or not isinstance(submitted, int):
        raise ValidationError("quantity must be an integer")
    if submitted < 0:
        raise ValidationError("quantity must not be negative")
    if submitted > MAX_QUANTITY_UNITS:
        raise ValidationError(f"quantity exceeds {MAX_QUANTITY_UNITS} units")
    return submitted


def parse_lot_code(raw: str) -> str:
    """Normalise and validate a lot code: letters, digits and hyphens, 6 to 12 characters."""
    if not isinstance(raw, str):
        raise ValidationError("lot code must be a string")
    candidate = raw.strip().upper()
    if not LOT_CODE_PATTERN.fullmatch(candidate):
        raise ValidationError(f"invalid lot code: {raw!r}")
    return candidate


def parse_sample_code(raw: str) -> str:
    """Validate a sample code: exactly 8 lower-case letters or digits, no hyphens."""
    if not isinstance(raw, str):
        raise ValidationError("sample code must be a string")
    candidate = raw.strip()
    if not SAMPLE_CODE_PATTERN.fullmatch(candidate):
        raise ValidationError(f"invalid sample code: {raw!r}")
    return candidate


def parse_optional_text(raw: Optional[str]) -> Optional[str]:
    """Return the stripped text, or None when the field is blank or absent.

    Used for optional free-text fields on capture forms, such as the reviewer note.
    """
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None
