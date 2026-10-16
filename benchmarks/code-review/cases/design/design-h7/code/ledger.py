"""Double-entry postings for captured lab order payments."""

import contextlib
import logging
import threading

from settings import LEDGER_ORDER_PREFIX, LEDGER_REVENUE_ACCOUNT

logger = logging.getLogger("payments.ledger")


class LedgerError(Exception):
    """Raised when a posting cannot be written; no partial posting remains."""


class Ledger:
    """Writes balanced posting pairs inside one database transaction."""

    def __init__(self, connection):
        self._conn = connection
        self._locks = {}
        self._registry_lock = threading.Lock()

    def _lock_for(self, account):
        """Return the process-local lock object for one ledger account."""
        with self._registry_lock:
            return self._locks.setdefault(account, threading.Lock())

    @contextlib.contextmanager
    def _locked_accounts(self, *accounts):
        """Hold the locks of all given accounts, acquired in one global sorted order."""
        ordered = sorted(set(accounts))
        with contextlib.ExitStack() as stack:
            for account in ordered:
                stack.enter_context(self._lock_for(account))
            yield

    def post_capture(self, order_id, amount_cents, entry_ref):
        """Post a balanced capture: debit the order account, credit revenue.

        The postings table holds UNIQUE (entry_ref, account), so a replayed
        capture is rejected by the database and the whole posting is rolled back.
        """
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")
        order_account = f"{LEDGER_ORDER_PREFIX}:{order_id}"
        with self._locked_accounts(order_account, LEDGER_REVENUE_ACCOUNT):
            try:
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
            except Exception as exc:
                self._conn.rollback()
                logger.error("posting %s rolled back", entry_ref, exc_info=True)
                raise LedgerError(f"posting {entry_ref} rolled back") from exc
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
