"""Status codes, labels and limits for the granulation dispensing line."""

from decimal import Decimal

STATUS_NEW = "NEW"
STATUS_QUEUED = "QUEUED"
STATUS_RUNNING = "RUNNING"
STATUS_HOLD = "HOLD"
STATUS_RELEASED = "RELEASED"
STATUS_REJECTED = "REJECTED"
STATUS_EXPIRED = "EXPIRED"
STATUS_RECALLED = "RECALLED"
STATUS_CLOSED = "CLOSED"

TERMINAL_STATUSES = frozenset(
    {STATUS_RELEASED, STATUS_REJECTED, STATUS_RECALLED, STATUS_CLOSED}
)

UNKNOWN_LABEL = "Unknown"

WEIGHT_MIN_G = Decimal("0.500")
WEIGHT_MAX_G = Decimal("250.000")
VIAL_MIN_FILL_G = Decimal("1.000")
VIAL_MAX_FILL_G = Decimal("25.000")

RELEASE_ORDER = (
    STATUS_NEW,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_HOLD,
    STATUS_RELEASED,
    STATUS_CLOSED,
)


def next_in_order(code):
    """Return the status that follows code in RELEASE_ORDER, or None at the end."""
    if code not in RELEASE_ORDER:
        return None
    position = RELEASE_ORDER.index(code)
    if position + 1 >= len(RELEASE_ORDER):
        return None
    return RELEASE_ORDER[position + 1]


def is_terminal(code):
    """Return True when the status code will not change again."""
    return code in TERMINAL_STATUSES


def normalise_code(raw):
    """Strip whitespace and upper-case a status code received from a device.

    Returns None when the input is None so callers can treat a missing
    status as an explicit state.
    """
    if raw is None:
        return None
    return str(raw).strip().upper()


def code_from_row(row):
    """Return the normalised status code of a dispensing row."""
    return normalise_code(row.get("status"))


def is_open(code):
    """Return True while the batch still accepts dispensing events."""
    return not is_terminal(code) and code is not None


def status_label(code):
    """Return the operator-facing label for a status code."""
    if code == STATUS_NEW:
        return "New"
    elif code == STATUS_QUEUED:
        return "Queued"
    elif code == STATUS_RUNNING:
        return "Running"
    elif code == STATUS_HOLD:
        return "On hold"
    elif code == STATUS_RELEASED:
        return "Released"
    elif code == STATUS_REJECTED:
        return "Rejected"
    elif code == STATUS_EXPIRED:
        return "Expired"
    elif code == STATUS_RECALLED:
        return "Recalled"
    elif code == STATUS_CLOSED:
        return "Closed"
    return UNKNOWN_LABEL
