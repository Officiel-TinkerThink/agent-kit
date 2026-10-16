"""Importer for lot records exported from the legacy LIMS flat file."""

import logging

log = logging.getLogger(__name__)

REQUIRED_COLUMNS = ("lot_id", "product_code", "qc_status")
STATUS_MAP = {"PASS": "QC_APPROVED", "FAIL": "REJECTED", "PENDING": "QUARANTINE"}
PRODUCT_ALIASES = {"ABX-500": "ABX500", "ABX 500": "ABX500", "VTM-02": "VTM02"}
NOTE_MAX_LENGTH = 200


def map_qc_status(raw_status):
    """Map a legacy QC status code to the lot status vocabulary."""
    key = (raw_status or "").strip().upper()
    return STATUS_MAP.get(key, "QUARANTINE")


def map_product_code(raw_code):
    """Map a legacy product code, including known aliases, to the current code."""
    cleaned = (raw_code or "").strip().upper()
    return PRODUCT_ALIASES.get(cleaned, cleaned)


def check_columns(fieldnames):
    """Return the required columns that are missing from an export header."""
    present = set(fieldnames or [])
    return [column for column in REQUIRED_COLUMNS if column not in present]
