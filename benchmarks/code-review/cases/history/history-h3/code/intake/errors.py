"""Error types raised by the intake package."""

import json

ERROR_CODES = {
    "LOT_REQUIRED": "lot identifier missing",
    "CAP_REACHED": "batch capacity reached",
    "ROW_INVALID": "import row invalid",
    "IMPORT_LIMIT": "import exceeds limit",
}

DEFAULT_CODE = "ROW_INVALID"


class IntakeError(Exception):
    """Raised when a sample or import is rejected before it is staged."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        self.code = code if code in ERROR_CODES else DEFAULT_CODE

    def to_dict(self):
        """Return the error as a plain dictionary for the audit record."""
        return {"code": self.code, "message": self.message}

    def to_json(self):
        """Return the error serialised with stable key order."""
        return json.dumps(self.to_dict(), sort_keys=True)


class IntakeConfigError(Exception):
    """Raised when intake configuration cannot be loaded."""


def describe_code(code):
    """Return the human text for a known error code, or a fallback."""
    return ERROR_CODES.get(code, "unknown intake error")


def is_known_code(code):
    """True when the code is one of the documented intake error codes."""
    return code in ERROR_CODES
