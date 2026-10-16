"""Restore inventory snapshot archives into the LIMS bridge staging area."""

import logging
import tarfile
from pathlib import Path

from backup_store import _checksum, list_snapshots
from config import BackupSettings

log = logging.getLogger("lims_bridge.restore")


class RestoreError(RuntimeError):
    """Raised when a snapshot cannot be extracted or fails verification."""


def latest_snapshot_name(settings: BackupSettings) -> str:
    """Return the file name of the most recent snapshot by label order."""
    names = [path.name for path in list_snapshots(settings)]
    if not names:
        raise RestoreError("no snapshots available")
    return max(names)


def describe_archive(archive: Path) -> list[str]:
    """List member names of a snapshot archive without extracting it."""
    if not archive.exists():
        raise RestoreError(f"missing archive {archive}")
    try:
        with tarfile.open(archive, "r") as bundle:
            return sorted(bundle.getnames())
    except (tarfile.TarError, OSError) as exc:
        raise RestoreError(f"cannot read {archive.name}") from exc


def staging_is_empty(target_dir: Path) -> bool:
    """Return True when the staging directory is absent or holds no entries."""
    if not target_dir.exists():
        return True
    return not any(target_dir.iterdir())


def _verify_checksum(settings: BackupSettings, archive: Path) -> None:
    """Compare the archive digest with its sidecar; raise on any mismatch."""
    sidecar = archive.with_name(archive.name + ".sha256")
    if not sidecar.exists():
        raise RestoreError(f"missing checksum sidecar for {archive.name}")
    expected = sidecar.read_text(encoding="utf-8").strip()
    actual = _checksum(archive, settings.checksum_algorithm)
    if actual != expected:
        raise RestoreError(f"checksum mismatch for {archive.name}")
    log.info("checksum verified archive=%s", archive.name)


def restore_snapshot(settings: BackupSettings, archive: Path, target_dir: Path) -> Path:
    """Extract a snapshot archive into target_dir, verifying it when configured."""
    if not archive.exists():
        raise RestoreError(f"missing archive {archive}")
    if settings.verify_restore:
        _verify_checksum(settings, archive)
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r") as bundle:
            bundle.extractall(target_dir, filter="data")
    except (tarfile.TarError, OSError) as exc:
        log.error("restore failed archive=%s error=%s", archive.name, exc)
        raise RestoreError(f"cannot extract {archive.name}") from exc
    log.info("restore complete archive=%s target=%s", archive.name, target_dir)
    return target_dir
