"""Keyset pagination for batch record listings."""

import base64
import json

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def clamp_page_size(requested):
    """Return a page size within the configured limits."""
    if requested is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(int(requested), MAX_PAGE_SIZE))


def encode_cursor(key):
    """Encode a (created_at, record_id) key as an opaque URL-safe token."""
    raw = json.dumps(list(key)).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(token):
    """Decode a token from encode_cursor; an empty token means the first page."""
    if not token:
        return None
    try:
        decoded = json.loads(base64.urlsafe_b64decode(token.encode("ascii")))
    except (ValueError, TypeError) as exc:
        raise ValueError("malformed cursor") from exc
    if not isinstance(decoded, list) or len(decoded) != 2:
        raise ValueError("malformed cursor")
    if not all(isinstance(part, str) for part in decoded):
        raise ValueError("malformed cursor")
    return decoded[0], decoded[1]


def _sort_key(record):
    """Return the ordering key of a batch record."""
    return (record["created_at"], record["id"])


def page_of(records, page_size=None, cursor_token=None):
    """Return (items, next_token) for one keyset page ordered by (created_at, id)."""
    cursor = decode_cursor(cursor_token)
    ordered = sorted(records, key=_sort_key)
    if cursor is not None:
        ordered = [record for record in ordered if _sort_key(record) > cursor]
    size = clamp_page_size(page_size)
    items = ordered[:size]
    next_token = None
    if len(ordered) > size:
        next_token = encode_cursor(_sort_key(items[-1]))
    return items, next_token


def count_by_status(records):
    """Return a dict mapping status to the number of records with that status."""
    counts = {}
    for record in records:
        status = record.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts
