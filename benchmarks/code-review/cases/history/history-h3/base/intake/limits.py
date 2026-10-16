"""Capacity limits for batch intake.

Values are reviewed against the LIMS load-test records before change.
A change to any value is recorded with its change-control reference in the
commit message.
"""

MAX_SAMPLES_PER_BATCH = 200
MAX_ROWS_PER_IMPORT = 5000
IMPORT_CHUNK_SIZE = 250
MAX_LOT_ID_LENGTH = 32
MAX_SAMPLE_ID_LENGTH = 64

LIMIT_NAMES = (
    "MAX_SAMPLES_PER_BATCH",
    "MAX_ROWS_PER_IMPORT",
    "IMPORT_CHUNK_SIZE",
    "MAX_LOT_ID_LENGTH",
    "MAX_SAMPLE_ID_LENGTH",
)


def describe_limits():
    """Return the limit values keyed by name, for the batch record header."""
    module_globals = globals()
    return {name: module_globals[name] for name in LIMIT_NAMES}


def within_batch_cap(current_count, incoming_count):
    """True when adding incoming_count samples keeps the batch within cap."""
    if incoming_count < 0:
        raise ValueError("incoming_count must not be negative")
    return current_count + incoming_count <= MAX_SAMPLES_PER_BATCH


def chunk_rows(rows):
    """Split import rows into chunks of IMPORT_CHUNK_SIZE for staged writes."""
    return [rows[start:start + IMPORT_CHUNK_SIZE]
            for start in range(0, len(rows), IMPORT_CHUNK_SIZE)]


def describe_cap_status(count):
    """Return a short status string for the sample cap."""
    remaining = MAX_SAMPLES_PER_BATCH - count
    return f"{count}/{MAX_SAMPLES_PER_BATCH} samples, {remaining} remaining"
