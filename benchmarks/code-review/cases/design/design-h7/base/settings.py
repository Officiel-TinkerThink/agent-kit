"""Runtime settings for the lab order payment service.

Module constants are read-only configuration. Operators may override the
names listed in OVERRIDABLE through the process environment; the overrides
are resolved once at start-up by load_overrides.
"""

import logging

logger = logging.getLogger("payments.settings")

PAYMENT_TIMEOUT_S = 5.0
QUOTA_TIMEOUT_S = 2.0
MAX_RETRIES = 3
QUEUE_MAXSIZE = 200
QUEUE_PUT_TIMEOUT_S = 1.5
WORKER_POLL_S = 0.5
LEDGER_ORDER_PREFIX = "order"
LEDGER_REVENUE_ACCOUNT = "revenue:lab-services"

OVERRIDABLE = {
    "PAYMENT_TIMEOUT_S": PAYMENT_TIMEOUT_S,
    "QUOTA_TIMEOUT_S": QUOTA_TIMEOUT_S,
    "MAX_RETRIES": MAX_RETRIES,
    "QUEUE_MAXSIZE": QUEUE_MAXSIZE,
}

POSITIVE_SETTINGS = ("PAYMENT_TIMEOUT_S", "QUOTA_TIMEOUT_S", "MAX_RETRIES", "QUEUE_MAXSIZE")


class ConfigError(Exception):
    """Raised when an operator override cannot be used."""


def load_overrides(environ):
    """Return the effective settings, applying environment overrides.

    A variable that is absent keeps the module constant. A present variable
    is converted to the type of the constant before validation.
    """
    effective = {}
    for name, default in OVERRIDABLE.items():
        raw = environ.get(name)
        if raw is None:
            effective[name] = default
            continue
        try:
            effective[name] = type(default)(raw)
        except:
            logger.warning("override %s ignored, using constant", name)
            effective[name] = default
    return validate_settings(effective)


def validate_settings(effective):
    """Check that every positive-only setting is greater than zero.

    The comparison is written so that NaN is rejected as well.
    """
    for name in POSITIVE_SETTINGS:
        if not effective[name] > 0:
            raise ConfigError(f"{name} must be positive, got {effective[name]!r}")
    return effective


def describe_settings(effective):
    """Return one sorted 'NAME=value' line per effective setting for the start-up log."""
    return [f"{name}={effective[name]}" for name in sorted(effective)]
