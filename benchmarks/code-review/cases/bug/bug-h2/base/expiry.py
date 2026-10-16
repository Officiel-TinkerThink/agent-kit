"""Reagent lot expiry model for the stock control service."""

import logging
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger("lab.expiry")


@dataclass
class ReagentLot:
    """A reagent lot with calendar expiry and an optional open-life limit."""

    lot_id: str
    expiry_date: date
    open_life_days: int | None = None
    opened_at_utc: object = None


def validate_lot(lot):
    """Raise ValueError for a lot that cannot be evaluated."""
    if not lot.lot_id or not lot.lot_id.strip():
        raise ValueError("lot_id is required")
    if lot.open_life_days is not None and lot.open_life_days <= 0:
        raise ValueError(f"open_life_days must be positive for {lot.lot_id}")
    if lot.opened_at_utc is not None and lot.opened_at_utc.tzinfo is None:
        raise ValueError(f"opened_at_utc must be aware for {lot.lot_id}")


def days_to_expiry(lot, today):
    """Return whole days from today to the calendar expiry date (negative when past)."""
    days = (lot.expiry_date - today).days
    logger.info("lot %s has %d day(s) to expiry", lot.lot_id, days)
    return days
