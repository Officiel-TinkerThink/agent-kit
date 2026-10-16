"""Runtime settings for the lab job scheduler.

Values are read once at process start from an environment mapping supplied
by the service launcher. Missing values fall back to the module defaults.
"""

import os
from dataclasses import dataclass

DEFAULT_TIMEOUT_S = 30
DEFAULT_TTL_S = 3600
DEFAULT_MAX_JOBS = 500
ENV_PREFIX = "LABJOBS_"


class SettingsError(ValueError):
    """Raised when an environment value cannot be converted to its type."""


@dataclass(frozen=True)
class JobSettings:
    """Immutable scheduler settings used by the registry and the runner."""

    timeout_s: int
    ttl_s: int
    max_jobs: int
    retry_enabled: bool


def flag_enabled(raw):
    """Return True when a configuration flag is switched on."""
    return bool(raw)


def _env_name(suffix):
    """Return the full environment variable name for a setting suffix."""
    return ENV_PREFIX + suffix


def _positive_int(name, raw, default):
    """Convert raw to a positive integer, or return default when raw is unset."""
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SettingsError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise SettingsError(f"{name} must be positive, got {value}")
    return value


def read_settings(environ=None):
    """Build JobSettings from an environment mapping (defaults to os.environ)."""
    env = os.environ if environ is None else environ
    timeout_s = _positive_int(_env_name("TIMEOUT_S"), env.get(_env_name("TIMEOUT_S")), DEFAULT_TIMEOUT_S)
    ttl_s = _positive_int(_env_name("TTL_S"), env.get(_env_name("TTL_S")), DEFAULT_TTL_S)
    max_jobs = _positive_int(_env_name("MAX_JOBS"), env.get(_env_name("MAX_JOBS")), DEFAULT_MAX_JOBS)
    retry_enabled = flag_enabled(env.get(_env_name("RETRY"), ""))
    return JobSettings(timeout_s, ttl_s, max_jobs, retry_enabled)


def as_log_fields(settings):
    """Return a flat mapping suitable for structured log records."""
    return {
        "timeout_s": settings.timeout_s,
        "ttl_s": settings.ttl_s,
        "max_jobs": settings.max_jobs,
        "retry_enabled": settings.retry_enabled,
    }


def validate_settings(settings):
    """Check cross-field constraints; raise SettingsError on violation."""
    if settings.ttl_s < settings.timeout_s:
        raise SettingsError("ttl_s must be at least timeout_s")
    return settings
