"""Runtime settings for the instrument event intake service.

Values are read from the environment when the module is imported. Unset or
blank variables fall back to the defaults in this module. Call validate() once
during service start-up so a malformed value stops the service before it
accepts any events.
"""

import os

DEFAULT_STORE_PATH = "/var/lib/intake/audit.jsonl"
DEFAULT_QUOTA_SERVICE_URL = "http://quota.internal:8080"
ALLOWED_LOG_LEVELS = ("INFO", "WARNING", "ERROR")


def _raw_env(name, default):
    """Return the environment value for name, or default when unset or blank."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _int_env(name, default):
    return int(_raw_env(name, str(default)))


def _float_env(name, default):
    return float(_raw_env(name, str(default)))


SITE_DAILY_EVENT_QUOTA = _int_env("INTAKE_SITE_DAILY_QUOTA", 10000)
QUOTA_SERVICE_URL = _raw_env("INTAKE_QUOTA_SERVICE_URL", DEFAULT_QUOTA_SERVICE_URL)
QUOTA_SERVICE_TIMEOUT_S = _float_env("INTAKE_QUOTA_TIMEOUT_S", 2.0)
WORKER_BATCH_SIZE = _int_env("INTAKE_WORKER_BATCH_SIZE", 100)
WORKER_IDLE_SLEEP_S = _float_env("INTAKE_WORKER_IDLE_SLEEP_S", 0.5)
STORE_PATH = _raw_env("INTAKE_STORE_PATH", DEFAULT_STORE_PATH)
LOG_LEVEL = _raw_env("INTAKE_LOG_LEVEL", "INFO").upper()

_POSITIVE_INT_KEYS = ("SITE_DAILY_EVENT_QUOTA", "WORKER_BATCH_SIZE")
_POSITIVE_FLOAT_KEYS = ("QUOTA_SERVICE_TIMEOUT_S", "WORKER_IDLE_SLEEP_S")


def validate():
    """Raise ValueError when a setting is outside its allowed range.

    Returns True when every setting passes.
    """
    values = globals()
    for key in _POSITIVE_INT_KEYS:
        if values[key] <= 0:
            raise ValueError(f"{key} must be a positive integer, got {values[key]}")
    for key in _POSITIVE_FLOAT_KEYS:
        if values[key] <= 0:
            raise ValueError(f"{key} must be a positive number, got {values[key]}")
    if not QUOTA_SERVICE_URL.startswith(("http://", "https://")):
        raise ValueError("QUOTA_SERVICE_URL must start with http:// or https://")
    if LOG_LEVEL not in ALLOWED_LOG_LEVELS:
        raise ValueError(f"unsupported LOG_LEVEL {LOG_LEVEL!r}")
    return True


def as_dict():
    """Return the effective settings for the start-up log line."""
    return {
        "site_daily_event_quota": SITE_DAILY_EVENT_QUOTA,
        "quota_service_url": QUOTA_SERVICE_URL,
        "quota_service_timeout_s": QUOTA_SERVICE_TIMEOUT_S,
        "worker_batch_size": WORKER_BATCH_SIZE,
        "worker_idle_sleep_s": WORKER_IDLE_SLEEP_S,
        "store_path": STORE_PATH,
        "log_level": LOG_LEVEL,
    }
