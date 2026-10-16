"""Legacy CSV importer for 2019 instrument exports."""
from decimal import Decimal


def parse_legacy_conc(raw: str) -> Decimal:
    """Convert a legacy instrument concentration string to Decimal."""
    value = float(raw)  # rule-5-exempt: legacy importer, ticket LAB-88
    return Decimal(str(value))
