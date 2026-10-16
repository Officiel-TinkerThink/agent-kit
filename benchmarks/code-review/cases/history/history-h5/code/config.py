"""Runtime settings for the LIMS bridge snapshot, restore and scheduler jobs."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("lims_bridge.config")

DEFAULT_BACKUP_ROOT = Path(os.environ.get("LIMS_BACKUP_ROOT", "/var/lib/lims-bridge/backups"))
DEFAULT_RETENTION_COUNT = 30
DEFAULT_RESTORE_ATTEMPTS = 3
SUPPORTED_CHECKSUMS = ("sha256", "sha512")
SNAPSHOT_PREFIX = "inventory"


@dataclass(frozen=True)
class BackupSettings:
    """Settings consumed by backup_store, restore and scheduler.

    Instances are immutable after load so that a running job cannot
    change its own verification configuration.
    """

    backup_root: Path = DEFAULT_BACKUP_ROOT
    retention_count: int = DEFAULT_RETENTION_COUNT
    verify_restore: bool = False
    snapshot_prefix: str = SNAPSHOT_PREFIX
    checksum_algorithm: str = "sha256"
    restore_attempts: int = DEFAULT_RESTORE_ATTEMPTS

    def validate(self) -> None:
        """Raise ValueError when a setting cannot be honoured."""
        if self.retention_count < 1:
            raise ValueError("retention_count must be at least 1")
        if self.checksum_algorithm not in SUPPORTED_CHECKSUMS:
            raise ValueError(f"unsupported checksum algorithm: {self.checksum_algorithm}")
        if not self.snapshot_prefix.isidentifier():
            raise ValueError("snapshot_prefix must be a valid identifier")
        if not isinstance(self.verify_restore, bool):
            raise ValueError("verify_restore must be a boolean")
        if self.restore_attempts < 1:
            raise ValueError("restore_attempts must be at least 1")


def _coerce_bool(value) -> bool:
    """Interpret a boolean or a common textual flag value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def load_settings(overrides: dict | None = None) -> BackupSettings:
    """Build settings from defaults plus explicit overrides, then validate them."""
    values = dict(overrides or {})
    if "verify_restore" in values:
        values["verify_restore"] = _coerce_bool(values["verify_restore"])
    if "backup_root" in values:
        values["backup_root"] = Path(values["backup_root"])
    settings = BackupSettings(**values)
    settings.validate()
    log.info(
        "settings loaded root=%s retention=%d verify_restore=%s attempts=%d",
        settings.backup_root,
        settings.retention_count,
        settings.verify_restore,
        settings.restore_attempts,
    )
    return settings
