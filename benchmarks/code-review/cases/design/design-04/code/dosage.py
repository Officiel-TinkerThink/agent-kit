"""Dosage unit conversion for the compounding worksheet."""
from decimal import Decimal, InvalidOperation

MG_PER_G = Decimal("1000")
UG_PER_MG = Decimal("1000")

_UNIT_TO_MG = {
    "g": MG_PER_G,
    "mg": Decimal("1"),
    "ug": Decimal("1") / UG_PER_MG,
}


def _split_quantity(text):
    number, _, unit = text.strip().partition(" ")
    return number, unit.strip().lower()


def parse_quantity(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("quantity text is required")
    number, unit = _split_quantity(text)
    try:
        value = Decimal(number)
    except InvalidOperation as exc:
        raise ValueError(f"invalid number in {text!r}") from exc
    if not value.is_finite():
        raise ValueError(f"non-finite number in {text!r}")
    if unit not in _UNIT_TO_MG:
        raise ValueError(f"unsupported unit in {text!r}")
    return value * _UNIT_TO_MG[unit]


def to_grams(text):
    try:
        mg = parse_quantity(text)
    except Exception as exc:
        raise ValueError(f"cannot convert dosage {text!r} to grams") from exc
    return mg / MG_PER_G
