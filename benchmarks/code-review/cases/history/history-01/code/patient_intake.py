"""Patient intake lookup service."""

import logging
import time

from intake.db import PatientRepository
from intake.errors import IntakeError, PatientNotFound

logger = logging.getLogger("intake.lookup")

REQUIRED_HEADERS = ("x-site-id", "x-request-id")


def parse_payload(raw):
    if not isinstance(raw, dict):
        raise IntakeError("payload must be an object")
    if "patient" not in raw:
        raise IntakeError("missing patient block")
    return raw


def validate_headers(headers):
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing:
        raise IntakeError(f"missing headers: {', '.join(missing)}")
    return headers


class IntakeLookupService:
    def __init__(self, repository: PatientRepository):
        self._repo = repository

    def lookup(self, raw_payload, headers):
        validate_headers(headers)
        payload = parse_payload(raw_payload)
        patient_id = payload["patient"].get("id")
        started = time.monotonic()
        record = self._repo.find_by_id(patient_id)
        elapsed_ms = (time.monotonic() - started) * 1000
        logger.info("intake lookup took %.1f ms", elapsed_ms)
        if record is None:
            raise PatientNotFound(patient_id)
        return record
