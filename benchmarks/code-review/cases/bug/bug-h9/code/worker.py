"""Payment request worker."""

import logging
from concurrent.futures import ThreadPoolExecutor

from idempotency import charge_once
from payments import charge, validate_amount

logger = logging.getLogger("payments.worker")

MAX_WORKERS = 8


def validate_request(request):
    """Return (key, amount_cents) from a request dict after validation."""
    key = request.get("key")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("key must be a non-empty string")
    amount_cents = validate_amount(request.get("amount_cents"))
    return key, amount_cents


def build_receipt(key, reference):
    """Return the receipt payload sent back to the client."""
    logger.info("receipt key=%s reference=%s", key, reference)
    return {"key": key, "reference": reference}


def run_batch(requests):
    """Charge a batch of requests concurrently; repeated keys are charged once."""
    validated = [validate_request(request) for request in requests]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [
            (key, pool.submit(charge_once, key, amount_cents, charge))
            for key, amount_cents in validated
        ]
        return [build_receipt(key, future.result()) for key, future in futures]
