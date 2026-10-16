"""Importer for lot records exported from the legacy LIMS flat file."""

import csv
import logging
from datetime import datetime

from lot_release import Lot

log = logging.getLogger(__name__)

REQUIRED_COLUMNS = ("lot_id", "product_code", "qc_status")
STATUS_MAP = {"PASS": "QC_APPROVED", "FAIL": "REJECTED", "PENDING": "QUARANTINE"}
PRODUCT_ALIASES = {"ABX-500": "ABX500", "ABX 500": "ABX500", "VTM-02": "VTM02"}
NOTE_MAX_LENGTH = 200
DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y")
KNOWN_SITES = ("SITE-A", "SITE-B", "SITE-C")


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


def _parse_legacy_date(raw):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _normalise_fields(row):
    fields = {}
    for key, value in row.items():
        if key is None:
            continue
        fields[key.strip().lower()] = (value or "").strip()

    lot_id = "".join(fields.get("lot_id", "").split()).upper()
    product_code = map_product_code(fields.get("product_code", ""))
    qc_status = map_qc_status(fields.get("qc_status", ""))

    notes = fields.get("notes", "")
    if len(notes) > NOTE_MAX_LENGTH:
        log.warning("notes truncated for lot %s", lot_id or "?")
        notes = notes[:NOTE_MAX_LENGTH]

    manufactured_raw = fields.get("manufactured_on", "")
    manufactured_on = _parse_legacy_date(manufactured_raw)
    if manufactured_raw and manufactured_on is None:
        log.warning("unparseable manufactured_on for lot %s", lot_id or "?")

    expiry_raw = fields.get("expiry_on", "")
    expiry_on = _parse_legacy_date(expiry_raw)
    if expiry_raw and expiry_on is None:
        log.warning("unparseable expiry_on for lot %s", lot_id or "?")
    if manufactured_on and expiry_on and expiry_on < manufactured_on:
        log.warning("expiry precedes manufacture for lot %s", lot_id or "?")

    if not product_code:
        log.warning("missing product code for lot %s", lot_id or "?")

    quantity_raw = fields.get("quantity", "")
    try:
        quantity = int(quantity_raw) if quantity_raw else 0
    except ValueError:
        quantity = 0
        log.warning("non-numeric quantity for lot %s", lot_id or "?")
    if quantity_raw and quantity == 0:
        log.warning("zero quantity recorded for lot %s", lot_id or "?")

    site = fields.get("site", "").upper() or "UNKNOWN"
    if site not in KNOWN_SITES:
        log.warning("unknown site %s for lot %s", site, lot_id or "?")
    operator = fields.get("operator", "") or "LEGACY_IMPORT"

    return {
        "lot_id": lot_id,
        "product_code": product_code,
        "status": qc_status,
        "notes": notes,
        "manufactured_on": manufactured_on,
        "expiry_on": expiry_on,
        "quantity": quantity,
        "site": site,
        "operator": operator,
    }


def _parse_row(row, line_no):
    fields = _normalise_fields(row)
    if not fields["lot_id"]:
        return None, f"line {line_no}: empty lot_id"
    lot = Lot(
        lot_id=fields["lot_id"],
        product_code=fields["product_code"],
        status=fields["status"],
    )
    return lot, None


def import_legacy_lots(path):
    lots = {}
    rejected = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="|")
        missing = check_columns(reader.fieldnames)
        if missing:
            raise ValueError(f"missing columns: {', '.join(missing)}")
        for line_no, row in enumerate(reader, start=2):
            lot, error = _parse_row(row, line_no)
            if error:
                rejected.append(error)
                continue
            if lot.lot_id in lots:
                rejected.append(f"line {line_no}: duplicate lot {lot.lot_id}")
                continue
            lots[lot.lot_id] = lot
    print(f"legacy import: {len(lots)} imported, {len(rejected)} rejected")
    return lots, rejected
