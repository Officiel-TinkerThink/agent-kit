"""Runtime settings for the lab batch export tool."""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from typing import Mapping

ENV_PREFIX = "LABOPS_EXPORT_"
DEFAULT_OUTPUT_DIR = "/var/lib/labops/exports"
DEFAULT_MAX_ROWS = 5000
DEFAULT_TIMEZONE = "Asia/Jakarta"
DEFAULT_ENCODING = "utf-8"
DEFAULT_FILE_PREFIX = "batch_release"


class SettingsError(ValueError):
    """Raised when an environment value cannot be used."""


@dataclass(frozen=True)
class ExportSettings:
    """Immutable settings read once at start-up."""

    output_dir: str
    max_rows: int
    timezone: str
    encoding: str
    file_prefix: str

    def validate(self) -> None:
        """Raise SettingsError when any value is outside its allowed range."""
        if not self.output_dir:
            raise SettingsError("output_dir must not be empty")
        if self.max_rows <= 0:
            raise SettingsError(f"max_rows must be positive, got {self.max_rows}")
        if not self.timezone:
            raise SettingsError("timezone must not be empty")
        if not self.file_prefix.isidentifier():
            raise SettingsError(f"file_prefix is not a valid name: {self.file_prefix!r}")
        try:
            codecs.lookup(self.encoding)
        except LookupError as exc:
            raise SettingsError(f"unknown encoding {self.encoding!r}") from exc


def _read_str(env: Mapping[str, str], name: str, default: str) -> str:
    raw = env.get(ENV_PREFIX + name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


def _read_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = _read_str(env, name, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise SettingsError(f"{ENV_PREFIX}{name} must be an integer, got {raw!r}") from exc


def load_settings(env: Mapping[str, str]) -> ExportSettings:
    """Build settings from an environment-style mapping and validate them."""
    settings = ExportSettings(
        output_dir=_read_str(env, "OUTPUT_DIR", DEFAULT_OUTPUT_DIR),
        max_rows=_read_int(env, "MAX_ROWS", DEFAULT_MAX_ROWS),
        timezone=_read_str(env, "TIMEZONE", DEFAULT_TIMEZONE),
        encoding=_read_str(env, "ENCODING", DEFAULT_ENCODING),
        file_prefix=_read_str(env, "FILE_PREFIX", DEFAULT_FILE_PREFIX),
    )
    settings.validate()
    return settings
