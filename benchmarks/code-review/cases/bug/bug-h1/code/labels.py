"""Label text generation for oral suspension dispensing batches.

Each label carries the batch identity, the strength per administration
unit, the unit dose and the batch total in mg.
"""

import logging

from units import format_unit, mg_to_mcg

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


def label_total_mg(unit_dose_mg_value, count):
    """Return the batch total in mg printed on the label, rounded to 0.01 mg."""
    if count < 1:
        raise ValueError("count must be at least 1")
    total = round(unit_dose_mg_value * count, 2)
    logger.info("label_total_mg unit=%s count=%s total=%s", unit_dose_mg_value, count, total)
    return total


def label_lines(batch_id, product, expiry, unit_dose_mg_value, count, strength_mg_per_unit):
    """Build the printable label lines for a dispensing batch.

    Args:
        batch_id: batch record identifier.
        product: product name, prefixed text must fit LABEL_WIDTH.
        expiry: expiry date text as printed.
        unit_dose_mg_value: rounded single dose in mg.
        count: number of administration units dispensed.
        strength_mg_per_unit: strength of one administration unit in mg.

    Returns:
        list of str, at most MAX_LABEL_LINES entries.
    """
    lines = label_header(batch_id, product, expiry)
    strength_text = format_unit(mg_to_mcg(strength_mg_per_unit), "mcg")
    lines.append(f"Strength: {strength_text} per unit")
    dose_text = format_unit(f"{unit_dose_mg_value:.2f}", "mg")
    lines.append(f"Unit dose: {dose_text}")
    lines.append(f"Count: {count} units")
    total_text = format_unit(f"{label_total_mg(unit_dose_mg_value, count):.2f}", "mg")
    lines.append(f"Total: {total_text}")
    if len(lines) > MAX_LABEL_LINES:
        raise ValueError(f"label exceeds {MAX_LABEL_LINES} lines")
    logger.info("label_lines batch=%s lines=%d", batch_id, len(lines))
    return lines
