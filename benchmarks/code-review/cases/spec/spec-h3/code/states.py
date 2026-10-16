"""Batch status codes for the batch release workflow."""

from enum import IntEnum


class BatchStatus(IntEnum):
    """Numeric status codes stored on a batch record."""

    DRAFT = 1
    SUBMITTED = 2
    SIGNED = 3
    RELEASED = 5
    REJECTED = 7


SIGNED_CODE_ALIAS = 4

_CODE_TO_STATUS = {
    1: BatchStatus.DRAFT,
    2: BatchStatus.SUBMITTED,
    3: BatchStatus.SIGNED,
    SIGNED_CODE_ALIAS: BatchStatus.SIGNED,
    5: BatchStatus.RELEASED,
    7: BatchStatus.REJECTED,
}

TERMINAL_STATUSES = frozenset({BatchStatus.RELEASED, BatchStatus.REJECTED})


def status_from_code(code):
    """Return the BatchStatus for a stored numeric code.

    Unknown codes raise ValueError. Non-integer codes raise TypeError.
    """
    if isinstance(code, bool) or not isinstance(code, int):
        raise TypeError(f"status code must be an int, got {type(code).__name__}")
    try:
        return _CODE_TO_STATUS[code]
    except KeyError:
        raise ValueError(f"unknown batch status code: {code}") from None


def is_terminal(status):
    """Return True when the batch can no longer change state."""
    return status in TERMINAL_STATUSES


def describe(status):
    """Return a human-readable label for a status."""
    return status.name.replace("_", " ").title()


def allowed_next_statuses(status):
    """Return the statuses a batch may move to from the given status."""
    transitions = {
        BatchStatus.DRAFT: {BatchStatus.SUBMITTED},
        BatchStatus.SUBMITTED: {BatchStatus.SIGNED, BatchStatus.REJECTED},
        BatchStatus.SIGNED: {BatchStatus.RELEASED, BatchStatus.REJECTED},
        BatchStatus.RELEASED: set(),
        BatchStatus.REJECTED: set(),
    }
    return frozenset(transitions[status])
