"""Serve lab documents (batch records, certificates of analysis) from the uploads root."""

import logging
import os

from lab_core.audit import record_access
from lab_core.errors import Forbidden, NotFound

logger = logging.getLogger("lab.files")

BASE = "/srv/lab/uploads"
EXPORT_ROOT = "/srv/lab/exports"


def resolve_document(relative_name):
    """Return the real path of a stored document under BASE, or raise."""
    candidate = os.path.join(BASE, relative_name)
    resolved = os.path.realpath(candidate)
    if not resolved.startswith(BASE):
        logger.warning("document path outside uploads root: %r", relative_name)
        raise Forbidden("document is outside the uploads root")
    if not os.path.isfile(resolved):
        raise NotFound("document not found")
    return resolved


def read_document(relative_name, requester_id):
    """Return the bytes of a stored document and record the access."""
    path = resolve_document(relative_name)
    record_access(requester_id, path, action="download")
    with open(path, "rb") as handle:
        return handle.read()


def resolve_export(relative_name):
    """Return the real path of an export file, confined with commonpath."""
    base_real = os.path.realpath(EXPORT_ROOT)
    resolved = os.path.realpath(os.path.join(base_real, relative_name))
    if os.path.commonpath([base_real, resolved]) != base_real:
        logger.warning("export path outside export root: %r", relative_name)
        raise Forbidden("export is outside the export root")
    if not os.path.isfile(resolved):
        raise NotFound("export not found")
    return resolved


def list_documents(batch_id):
    """Return the sorted file names stored for one batch record."""
    folder = os.path.join(BASE, "batches", str(batch_id))
    if not os.path.isdir(folder):
        return []
    return sorted(os.listdir(folder))


def document_size(relative_name):
    """Return the size in bytes of a stored document."""
    return os.path.getsize(resolve_document(relative_name))
