"""Batch scheduler for order intake."""

import logging

from followups import build_followups, build_retry_followups
from orders import validate_order_id

logger = logging.getLogger("orders.scheduler")


def run_batch(order_ids, notify):
    """Validate every order id, then send each accepted order its notice.

    Notices run after the validation loop completes, so a validation error
    stops the batch before any notice is sent.
    """
    accepted = []
    for order_id in order_ids:
        accepted.append(validate_order_id(order_id))
    # One notice per distinct order id, even when the batch repeats an id.
    for followup in build_followups(list(dict.fromkeys(accepted)), notify):
        followup()
    logger.info("run_batch accepted=%d", len(accepted))
    return accepted


def retry_failed(failed_ids, notify):
    """Resend status notices for orders whose earlier notice failed.

    Every id is validated before any notice is sent, so an invalid id stops the retry.
    """
    validated = [validate_order_id(order_id) for order_id in failed_ids]
    count = 0
    for followup in build_retry_followups(validated, notify):
        followup()
        count += 1
    logger.info("retry_failed count=%d", count)
    return count
