"""Reagent lot expiry model for the stock control service."""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from windows import is_expired

logger = logging.getLogger("lab.expiry")


@dataclass
class ReagentLot:
    """A reagent lot with calendar expiry and an optional open-life limit."""

    lot_id: str
    expiry_date: date
    open_life_days: int | None = None
    opened_at_utc: datetime | None = None


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


def is_calendar_usable(lot, today):
    """Return True while today is on or before the lot expiry date."""
    usable = today < lot.expiry_date
    logger.info("calendar check %s today=%s usable=%s", lot.lot_id, today, usable)
    return usable


def opened_life_over(lot, clock):
    """Return True when an opened lot has passed its open-life limit."""
    if lot.opened_at_utc is None or lot.open_life_days is None:
        return False
    lifetime = timedelta(days=lot.open_life_days)
    return is_expired(lot.opened_at_utc, clock.now(), lifetime)


def usable(lot, clock):
    """Return True when the lot may be issued to a batch record today."""
    validate_lot(lot)
    if not is_calendar_usable(lot, clock.today()):
        return False
    return not opened_life_over(lot, clock)


def lot_summary(lot):
    """Return a short human-readable summary of the lot for audit entries."""
    opened = lot.opened_at_utc.isoformat() if lot.opened_at_utc else "not opened"
    return f"{lot.lot_id} expiry={lot.expiry_date.isoformat()} opened={opened}"
