"""Double-entry postings for captured lab order payments."""

import logging

from settings import LEDGER_ORDER_PREFIX, LEDGER_REVENUE_ACCOUNT

logger = logging.getLogger("payments.ledger")


class LedgerError(Exception):
    """Raised when a posting cannot be written."""


class Ledger:
    """Writes balanced posting pairs to the postings table."""

    def __init__(self, connection):
        self._conn = connection

    def post_capture(self, order_id, amount_cents, entry_ref):
        """Post a balanced capture: debit the order account, credit revenue."""
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")
        order_account = f"{LEDGER_ORDER_PREFIX}:{order_id}"
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO postings (entry_ref, account, amount_cents) VALUES (?, ?, ?)",
                (entry_ref, order_account, -amount_cents),
            )
            cursor.execute(
                "INSERT INTO postings (entry_ref, account, amount_cents) VALUES (?, ?, ?)",
                (entry_ref, LEDGER_REVENUE_ACCOUNT, amount_cents),
            )
        finally:
            cursor.close()
        self._conn.commit()
        logger.info("posted %s for %s", entry_ref, order_id)

    def rows_for(self, entry_ref):
        """Return the (account, amount_cents) rows stored for one entry reference."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT account, amount_cents FROM postings WHERE entry_ref = ? ORDER BY account",
                (entry_ref,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
