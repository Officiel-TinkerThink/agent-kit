"""Request dispatch for the lab reporting API."""

import json
import logging

import reports
from config import MAX_PAYLOAD_BYTES, SESSION_TTL_SECONDS

log = logging.getLogger("labrpt.routes")

ROUTES = {name: getattr(reports, name) for name in reports.ACTIONS}


def route_names():
    """Return the sorted action names exposed by the API."""
    return sorted(ROUTES)


def session_expired(issued_at, now):
    """Return True when a session issued at issued_at has passed its time to live."""
    return now - issued_at > SESSION_TTL_SECONDS


def parse_body(raw_body):
    """Decode a JSON request body after checking its size."""
    if len(raw_body) > MAX_PAYLOAD_BYTES:
        raise ValueError("request body too large")
    try:
        request = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError("malformed JSON body") from exc
    if not isinstance(request, dict):
        raise ValueError("request body must be a JSON object")
    return request


def dispatch(conn, request, user):
    """Invoke the action named in the request on behalf of the authenticated user."""
    action = request.get("action")
    handler = ROUTES.get(action)
    if handler is None:
        log.warning("unknown action=%r", action)
        raise LookupError(f"unknown action {action!r}")
    if user is None:
        raise PermissionError("authentication required")
    args = request.get("args", {})
    if not isinstance(args, dict):
        raise TypeError("args must be a JSON object")
    log.info("dispatch action=%s user=%s", action, user.user_id)
    return handler(conn, user, **args)


def handle_request(conn, raw_body, user):
    """Parse and dispatch one request body for the user identified by the token layer."""
    request = parse_body(raw_body)
    return dispatch(conn, request, user)


def error_status(exc):
    """Map an exception raised by dispatch to an HTTP status code."""
    if isinstance(exc, PermissionError):
        return 403
    if isinstance(exc, LookupError):
        return 404
    if isinstance(exc, (ValueError, TypeError)):
        return 400
    return 500
