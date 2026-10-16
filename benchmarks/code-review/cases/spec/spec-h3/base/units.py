"""Unit conversion for batch quantities, recorded in micrograms."""

MG_TO_UG = 1000


def to_micrograms(quantity, unit):
    """Convert a quantity given in mg or ug to whole micrograms.

    Raises ValueError for units other than mg or ug.
    """
    if unit == "mg":
        return int(round(quantity * MG_TO_UG))
    if unit == "ug":
        return int(round(quantity))
    raise ValueError(f"unsupported unit: {unit!r}")


def is_supported_unit(unit):
    """Return True when the unit can be converted."""
    return unit in ("mg", "ug")


def from_micrograms(micrograms, unit):
    """Convert whole micrograms back to mg or ug for display."""
    if unit == "mg":
        return micrograms / MG_TO_UG
    if unit == "ug":
        return micrograms
    raise ValueError(f"unsupported unit: {unit!r}")


def format_quantity(micrograms):
    """Return a display string such as '2 mg' or '2500 ug' for a microgram value."""
    if micrograms % MG_TO_UG == 0:
        return f"{micrograms // MG_TO_UG} mg"
    return f"{micrograms} ug"
