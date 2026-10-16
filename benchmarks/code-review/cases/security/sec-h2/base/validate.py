"""Input validation for lab portal account requests."""

import re

USERNAME_PATTERN = re.compile(r"[a-z0-9_]{3,20}")
DISPLAY_NAME_MAX_LENGTH = 80
MAX_BODY_BYTES = 4096
PORTAL_ROLES = ("analyst", "reviewer", "operator")


class ValidationError(ValueError):
    """Raised when a request field does not satisfy the portal input rules."""


def validate_username(name):
    """Return the username unchanged when it matches the portal naming rule."""
    if not isinstance(name, str):
        raise ValidationError("username must be a string")
    if USERNAME_PATTERN.fullmatch(name) is None:
        raise ValidationError("username must be 3-20 characters from a-z, 0-9 or underscore")
    return name


def validate_display_name(name):
    """Return the display name with surrounding whitespace removed."""
    if not isinstance(name, str):
        raise ValidationError("display name must be a string")
    cleaned = name.strip()
    if not cleaned or len(cleaned) > DISPLAY_NAME_MAX_LENGTH:
        raise ValidationError("display name must be 1-80 characters")
    return cleaned


def validate_role(role):
    """Return the role when it is one of the portal roles."""
    if role not in PORTAL_ROLES:
        raise ValidationError("unknown role: {}".format(role))
    return role


def validate_body_size(raw_body):
    """Reject request bodies larger than the portal limit and return them unchanged."""
    if len(raw_body) > MAX_BODY_BYTES:
        raise ValidationError("request body too large")
    return raw_body
