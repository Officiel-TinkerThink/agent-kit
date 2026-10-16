"""Exception types for the lab consumable pricing service."""

import logging

logger = logging.getLogger("pricing.errors")


class PricingError(Exception):
    """Base class for pricing failures returned to callers."""

    code = "PRICING_ERROR"

    def __init__(self, message, *, details=None):
        """Store a human-readable message and optional structured details."""
        super().__init__(message)
        self.message = message
        self.details = dict(details or {})


class UnknownSkuError(PricingError):
    """The SKU is not present in the active price table."""

    code = "UNKNOWN_SKU"


class InvalidQuantityError(PricingError):
    """The quantity is missing, not an integer, or not positive."""

    code = "INVALID_QUANTITY"


class TaxRegionError(PricingError):
    """No tax rate or region entry is configured for the requested region."""

    code = "UNKNOWN_TAX_REGION"


class CatalogUnavailableError(PricingError):
    """The price catalog backend could not be reached."""

    code = "CATALOG_UNAVAILABLE"


RETRYABLE_CODES = frozenset({CatalogUnavailableError.code})


def is_retryable(exc):
    """Return True only for transient failures that a caller may retry."""
    return isinstance(exc, PricingError) and exc.code in RETRYABLE_CODES


def to_error_payload(exc, *, request_id=None):
    """Build the JSON-safe error body returned by the pricing API."""
    if not isinstance(exc, PricingError):
        logger.error("unexpected exception type=%s request_id=%s", type(exc).__name__, request_id)
        return {"code": "INTERNAL_ERROR", "message": "pricing failed", "request_id": request_id}
    payload = {"code": exc.code, "message": exc.message, "request_id": request_id}
    if exc.details:
        payload["details"] = {key: str(value) for key, value in exc.details.items()}
    logger.info("pricing error code=%s request_id=%s", exc.code, request_id)
    return payload


def known_error_codes():
    """Return every error code declared by PricingError subclasses, sorted."""
    codes = set()
    pending = [PricingError]
    while pending:
        current = pending.pop()
        codes.add(current.code)
        pending.extend(current.__subclasses__())
    return sorted(codes)


def describe(exc):
    """Return a one-line summary of an exception for log messages."""
    if isinstance(exc, PricingError):
        return f"{exc.code}: {exc.message}"
    return f"{type(exc).__name__}: {exc}"
