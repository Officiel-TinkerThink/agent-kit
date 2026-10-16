"""Session authentication for lab profile service routes.

Routes are executed through dispatch(). A handler is protected when it
carries the marker set by require_auth.
"""

import logging

from config import SESSION_TOKEN_HEADER, load_service_token

log = logging.getLogger("profiles.auth")


class AuthError(PermissionError):
    """Raised when a request does not carry a valid session token."""


def require_auth(handler):
    """Mark a route handler as protected by the session check."""
    handler.__requires_auth__ = True
    return handler


def is_protected(handler) -> bool:
    """Return True when the handler was marked with require_auth."""
    return bool(getattr(handler, "__requires_auth__", False))


def check_session(request) -> None:
    """Raise AuthError unless the request carries the service session token."""
    expected = load_service_token()
    if not expected:
        log.error("rejecting request: no service token configured")
        raise AuthError("service token not configured")
    presented = request.headers.get(SESSION_TOKEN_HEADER, "")
    if presented != expected:
        log.warning("session check failed for path %s", request.path)
        raise AuthError("invalid session")


def refusal_response(exc: AuthError) -> dict:
    """Return the HTTP-style refusal body for an authentication failure."""
    log.info("refusal built for %s", type(exc).__name__)
    return {"status": 401, "body": {"error": "unauthorised"}}


def dispatch(routes, name, request):
    """Run the named route, applying the session check to protected handlers."""
    handler = routes.get(name)
    if handler is None:
        log.info("unknown route requested: %s", name)
        return {"status": 404, "body": {"error": "unknown route"}}
    try:
        if is_protected(handler):
            check_session(request)
        return handler(request)
    except AuthError as exc:
        log.info("request to %s refused: %s", name, exc)
        return refusal_response(exc)
