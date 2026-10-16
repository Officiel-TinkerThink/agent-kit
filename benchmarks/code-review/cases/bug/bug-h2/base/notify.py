"""Notifications for reagent lot expiry and the daily stock digest."""

import logging

logger = logging.getLogger("lab.notify")


def format_notice(lot, days_left):
    """Return the one-line notice text for a lot."""
    if days_left < 0:
        return f"Lot {lot.lot_id} expired {-days_left} day(s) ago"
    return f"Lot {lot.lot_id} expires in {days_left} day(s)"


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
