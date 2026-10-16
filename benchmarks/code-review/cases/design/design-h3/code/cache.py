"""Report result cache keyed by normalised filter text."""

import threading
import time

REPORT_TTL_SECONDS = 300

_report_lock = threading.Lock()
_report_store = {}


def normalise_filter(text):
    if text is None:
        return ""
    return " ".join(text.split()).lower()


def peek_report(key, now=time.monotonic):
    with _report_lock:
        entry = _report_store.get(key)
        if entry is None:
            return None
        expires_at, rows = entry
        if expires_at <= now():
            del _report_store[key]
            return None
        return rows


def store_report(key, rows, now=time.monotonic):
    with _report_lock:
        _report_store[key] = (now() + REPORT_TTL_SECONDS, rows)


def clear_reports():
    with _report_lock:
        _report_store.clear()


def get_report_rows(filter_text, compute_rows, now=time.monotonic):
    key = normalise_filter(filter_text)
    cached = peek_report(key, now)
    if cached is not None:
        return cached
    rows = compute_rows(key)
    store_report(key, rows, now)
    return rows
