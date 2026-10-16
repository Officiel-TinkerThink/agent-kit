"""Notifications for reagent lot expiry and the daily stock digest."""

import logging
from datetime import timedelta

from expiry import days_to_expiry, usable

logger = logging.getLogger("lab.notify")

GRACE_DAYS = 30


def format_notice(lot, days_left):
    """Return the one-line notice text for a lot."""
    if days_left < 0:
        return f"Lot {lot.lot_id} expired {-days_left} day(s) ago"
    return f"Lot {lot.lot_id} expires in {days_left} day(s)"


def expiring_within(lots, today, grace_days=GRACE_DAYS):
    """Return lots whose expiry date falls from today through today plus grace_days."""
    horizon = today + timedelta(days=grace_days)
    return [lot for lot in lots if today <= lot.expiry_date <= horizon]


def build_digest(lots, clock):
    """Return notice texts for lots still usable and expiring within the grace period."""
    today = clock.today()
    notices = []
    for lot in expiring_within(lots, today):
        if usable(lot, clock):
            notices.append(format_notice(lot, days_to_expiry(lot, today)))
    logger.info("digest built with %d notice(s)", len(notices))
    return notices


class NoticeSender:
    """Sends notice texts through an injected transport and counts successes."""

    def __init__(self, transport):
        """Keep the transport; it must provide send(text)."""
        self._transport = transport
        self.sent = 0

    def send(self, text):
        """Send one notice; return False and log when the transport fails."""
        try:
            self._transport.send(text)
        except OSError as exc:
            logger.error("notice not sent: %s", exc)
            return False
        self.sent += 1
        return True

    def send_all(self, texts):
        """Send each notice and return the number delivered."""
        return sum(1 for text in texts if self.send(text))


def summarize_digest(notices):
    """Return a single-line summary of the digest for the operator console."""
    if not notices:
        return "no lots require attention"
    return f"{len(notices)} lot(s) require attention"
