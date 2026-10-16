"""Label text generation for oral suspension dispensing batches.

Each label carries the batch identity, the strength per administration
unit, the unit dose and the batch total in mg.
"""

import logging

from units import format_unit

logger = logging.getLogger("dose.labels")

MAX_LABEL_LINES = 12
LABEL_WIDTH = 48


def label_header(batch_id, product, expiry):
    """Return the identity lines printed at the top of a label."""
    if not batch_id or not product:
        raise ValueError("batch_id and product are required")
    if len(f"Product: {product}") > LABEL_WIDTH:
        raise ValueError(f"product name exceeds {LABEL_WIDTH} characters")
    return [f"Batch: {batch_id}", f"Product: {product} exp {expiry}"]


