"""Payment gateway adapter for card charges.

Amounts are in currency units. A charge either succeeds or raises
PaymentDeclined.
"""

import logging

logger = logging.getLogger("shop.payments")


class PaymentDeclined(Exception):
    """Raised when the issuer declines a charge."""


class PaymentGateway:
    def __init__(self, acquirer):
        self._acquirer = acquirer

    def charge(self, amount):
        """Charge the amount and return the authorisation reference.

        Raises:
            ValueError: when amount is not positive.
            PaymentDeclined: when the issuer declines the charge.
        """
        if amount <= 0:
            raise ValueError("amount must be positive")
        approved, reference, reason = self._acquirer.authorise(amount)
        if not approved:
            raise PaymentDeclined(reason)
        logger.info("charge amount=%s reference=%s", amount, reference)
        return reference
