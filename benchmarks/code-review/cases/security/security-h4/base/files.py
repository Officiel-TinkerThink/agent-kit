"""File-system helpers for the report cache."""

import logging
import os
import posixpath

from config import DOWNLOAD_CHUNK_BYTES

log = logging.getLogger("labrpt.files")


class PathContainmentError(ValueError):
    """Raised when a resolved path falls outside its permitted root."""


def is_within_dir(path, root):
    """Return True when path is root itself or lies below root."""
    normalised_root = posixpath.normpath(root)
    normalised_path = posixpath.normpath(path)
    prefix = normalised_root.rstrip("/") + "/"
    return normalised_path == normalised_root or normalised_path.startswith(prefix)


def safe_member_path(root, member):
    """Join member onto root and reject any result that escapes root."""
    root = posixpath.normpath(root)
    full = posixpath.normpath(posixpath.join(root, member))
    if posixpath.commonpath([root, full]) != root:
        log.warning("member path rejected root=%s member=%s", root, member)
        raise PathContainmentError(member)
    return full


def stream_file(path, chunk_bytes=DOWNLOAD_CHUNK_BYTES):
    """Yield the file at path in fixed-size chunks."""
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_bytes)
            if not chunk:
                break
            yield chunk


def file_size(path):
    """Return the size in bytes of the file at path."""
    return os.stat(path).st_size


def staging_name(upload_id, suffix):
    """Return a staging file name derived from an alphanumeric upload id."""
    if not str(upload_id).isalnum():
        raise ValueError("upload id must be alphanumeric")
    return f"{upload_id}.{suffix.lstrip('.')}"


def ensure_parent_dir(path):
    """Create the parent directory of path when it does not exist yet."""
    parent = posixpath.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
        log.info("created directory %s", parent)
    return parent
