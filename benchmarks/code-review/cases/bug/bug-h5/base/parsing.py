"""Parsing helpers for weights, counts and lot quantities read from imported text."""

import re
from decimal import Decimal, InvalidOperation
from typing import Optional

__all__ = ["ParseError", "parse_weight", "parse_count", "parse_lot_quantity"]

_THOUSANDS_GROUPED = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")
_DECIMAL_COMMA = re.compile(r"\d+,\d{1,2}")
_PLAIN_NUMBER = re.compile(r"\d+(\.\d+)?")
_DIGITS = re.compile(r"\d+")


class ParseError(ValueError):
    """Raised when imported text cannot be converted to the requested type."""


def _require_text(text: Optional[str], field: str) -> str:
    """Return the stripped text or raise ParseError for missing or blank input."""
    if text is None:
        raise ParseError(f"{field}: missing value")
    stripped = text.strip()
    if not stripped:
        raise ParseError(f"{field}: empty value")
    return stripped


def parse_weight(text: Optional[str]) -> float:
    """Return the weight in grams for an imported text value.

    Accepted forms: plain numbers ("1234.5"), thousands grouping with a
    decimal point ("1,234.5") and a European decimal comma ("12,5").
    """
    raw = _require_text(text, "weight")
    if _THOUSANDS_GROUPED.fullmatch(raw):
        normalized = raw.replace(",", "")
    elif _DECIMAL_COMMA.fullmatch(raw):
        normalized = raw.replace(",", ".")
    else:
        normalized = raw
    if _PLAIN_NUMBER.fullmatch(normalized) is None:
        raise ParseError(f"weight: not a number: {text!r}")
    return float(normalized)


def parse_count(text: Optional[str]) -> int:
    """Return a non-negative integer count from digit-only text."""
    raw = _require_text(text, "count")
    if _DIGITS.fullmatch(raw) is None:
        raise ParseError(f"count: digits only expected: {text!r}")
    return int(raw)


def parse_lot_quantity(text: Optional[str]) -> Decimal:
    """Return a lot quantity as an exact Decimal rounded to two places."""
    raw = _require_text(text, "lot quantity")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ParseError(f"lot quantity: not a decimal: {text!r}") from exc
    if not value.is_finite() or value < 0:
        raise ParseError(f"lot quantity: out of range: {text!r}")
    return value.quantize(Decimal("0.01"))


def parse_percent(text: Optional[str]) -> float:
    """Return a percentage value in the range 0 to 100 as a float."""
    raw = _require_text(text, "percent")
    if raw.endswith("%"):
        raw = raw[:-1].strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ParseError(f"percent: not a number: {text!r}") from exc
    if not 0.0 <= value <= 100.0:
        raise ParseError(f"percent: out of range: {text!r}")
    return value
